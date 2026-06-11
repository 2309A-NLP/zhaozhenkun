# RAGFlow DeepDoc 模块技术分析文档

## 目录

1. [PDF 解析流程与分块策略](#1-pdf-解析流程与分块策略)
2. [do_handle_task 函数分析](#2-do_handle_task-函数分析)
3. [DeepDoc 模块解析器分析](#3-deepdoc-模块解析器分析)
4. [附录：代码文件索引](#4-附录代码文件索引)
5. [补充分析：源码级细节补充](#5-补充分析源码级细节补充基于-ragflow-最新源码)
   - 5.1 parser_id 与任务分页策略
   - 5.2 Redis Stream 消息队列完整实现
   - 5.3 do_handle_task 函数完整分支分析
   - 5.4 DeepDoc PDF 解析 7 步流程完整代码级分析
   - 5.5 补充解析器一览
   - 5.6 ParserType 完整枚举
   - 5.7 PDF 解析器注册表（PARSERS）
6. [工单验收对照检查表](#6-工单验收对照检查表)

---

## 1. PDF 解析流程与分块策略

### 1.1 概述

RAGFlow 的 PDF 解析流程分为三个主要阶段：

1. **任务创建与入队**：API 层创建解析任务，将任务消息通过 Redis Stream 推送到消息队列
2. **任务消费与分块**：Task Executor 从 Redis Stream 消费消息，调用 `chunk()` 函数执行文档解析与分块
3. **向量化与索引**：对分块结果进行 Embedding 向量化，写入文档存储（Elasticsearch/Infinity）

### 1.2 任务创建与入队（Redis Stream）

#### 1.2.1 队列命名规则

队列名称由 `get_svr_queue_name()` 函数生成，格式为 `{SVR_QUEUE_NAME}.{priority}.common`：

- 文件：`/tmp/ragflow/common/settings.py`，第 136-154 行
- 高优先级队列：`te.1.common`
- 低优先级队列：`te.0.common`

```python
def get_svr_queue_name(priority: int, suffix: str = "common") -> str:
    return f"{SVR_QUEUE_NAME}.{priority}.common"
```

`get_svr_queue_names()`（第 157-159 行）按优先级从高到低返回队列列表：
```python
def get_svr_queue_names(suffix:str):
    return [get_svr_queue_name(priority, suffix) for priority in [1, 0]]
```

#### 1.2.2 任务入队流程

**文档解析任务入队**：

- 文件：`/tmp/ragflow/api/db/services/task_service.py`，第 456-463 行

```python
unfinished_task_array = [task for task in parse_task_array if task["progress"] < 1.0]
for unfinished_task in unfinished_task_array:
    assert REDIS_CONN.queue_product(
        settings.get_svr_queue_name(priority, suffix), message=unfinished_task
    ), "Can't access Redis. Please check the Redis' status."
```

**知识图谱/RAPTOR 任务入队**：

- 文件：`/tmp/ragflow/api/db/services/document_service.py`，第 1101 行

```python
assert REDIS_CONN.queue_product(
    settings.get_svr_queue_name(priority, ty), message=task
), "Can't access Redis. Please check the Redis' status."
```

**Dataflow 任务入队**：

- 文件：`/tmp/ragflow/api/db/services/task_service.py`，第 552-554 行

```python
if not REDIS_CONN.queue_product(
        settings.get_svr_queue_name(priority, "common"), message=task
):
    return False, "Can't access Redis. Please check the Redis' status."
```

#### 1.2.3 Redis Stream 核心操作

`RedisDB` 类定义在 `/tmp/ragflow/rag/utils/redis_conn.py`：

- **`queue_product()`**（第 397-408 行）：使用 `XADD` 命令将消息写入 Redis Stream
- **`queue_consumer()`**（第 410-455 行）：使用 `XREADGROUP` 命令以消费者组方式消费消息
- **`get_unacked_iterator()`**（第 457-481 行）：遍历未确认的消息

```python
def queue_product(self, queue, message) -> bool:
    for _ in range(3):
        try:
            payload = {"message": json.dumps(message)}
            self.REDIS.xadd(queue, payload)
            return True
        except Exception as e:
            ...
    return False
```

`RedisMsg` 类（第 37-57 行）封装了 Redis Stream 消息，提供 `ack()` 方法确认消息已处理。

#### 1.2.4 任务消费流程

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`

**`handle_task()` 函数**（第 1704-1771 行）：

1. 调用 `collect()`（第 199-261 行）从 Redis Stream 获取消息
2. 通过 `redis_msg.ack()` 在任务完成后确认消息（第 1770 行）
3. 根据运行模式调用 `do_handle_task()` 或 `TaskManager.run_refactored_task()`

**`main()` 函数**（第 1870-1925 行）：事件循环，持续从队列中获取并执行任务。

### 1.3 解析器类型与 FACTORY 映射

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 115-132 行

```python
FACTORY = {
    "general": naive,
    ParserType.NAIVE.value: naive,
    ParserType.PAPER.value: paper,
    ParserType.BOOK.value: book,
    ParserType.PRESENTATION.value: presentation,
    ParserType.MANUAL.value: manual,
    ParserType.LAWS.value: laws,
    ParserType.QA.value: qa,
    ParserType.TABLE.value: table,
    ParserType.RESUME.value: resume,
    ParserType.PICTURE.value: picture,
    ParserType.ONE.value: one,
    ParserType.AUDIO.value: audio,
    ParserType.EMAIL.value: email,
    ParserType.KG.value: naive,   # knowledge_graph 使用 naive 分块策略
    ParserType.TAG.value: tag
}
```

ParserType 枚举定义在 `/tmp/ragflow/common/constants.py`，第 101-116 行：
- `PAPER = "paper"`
- `TABLE = "table"`
- `ONE = "one"`
- `KG = "knowledge_graph"`（实际上映射到 naive）

### 1.4 分块策略详解

#### 1.4.1 `paper` 策略

- 文件：`/tmp/ragflow/rag/app/paper.py`，第 149-261 行（`chunk()` 函数）

**流程**：
1. 使用 DeepDoc PDF 解析器（`Pdf()` 类，第 31-146 行）执行 OCR → 布局分析 → 表格识别 → 文本合并
2. 提取论文标题、作者、摘要
3. 摘要作为独立块，标记 `important_kwd` 为 `["abstract", "总结", "概括", "summary", "summarize"]`
4. 分区（sections）按 bullet 标题频率聚类，`bullets_category()` 检测标题层级（第 235 行）
5. `title_frequency()` 分析标题层级，`most_level` 作为分割基准（第 236 行）
6. 同一章节的内容合并为一个块（第 246-255 行）
7. 调用 `tokenize_chunks()` 对合并后的块进行分词处理（第 255 行）
8. 支持表格和图片的上下文附加（`attach_media_context()`，第 258-259 行）

**默认配置**：`chunk_token_num: 512`, `delimiter: "\n!?。；！？"`, `layout_recognize: "DeepDOC"`

#### 1.4.2 `table` 策略

- 文件：`/tmp/ragflow/rag/app/table.py`，第 59-167 行（`chunk()` 函数）

**流程**：
1. 支持 docx、pdf、excel、txt、html 等文件格式
2. **PDF 解析**：使用 DeepDoc OCR + 布局识别 → 表格结构识别 → 文本合并
3. **核心特点**：整个文件形成一个块，保持原始文本顺序（第 62 行注释："One file forms a chunk which maintains original text order"）
4. 调用 `tokenize()` 对整个文档进行分词（第 166 行）
5. 返回一个包含完整文档内容的块
6. 对于 TCADP/Docling/MinerU/PaddleOCR 解析器，设置 `chunk_token_num = 0`（第 116-117 行）

#### 1.4.3 `one` 策略

- 文件：`/tmp/ragflow/rag/app/one.py`，第 59-167 行（`chunk()` 函数）

**流程**：
1. 支持 docx、pdf、excel、txt、html 等多种格式（第 61 行注释）
2. 语义上与 `table` 类似——"One file forms a chunk which maintains original text order"（第 62 行）
3. 解析后的内容直接合并为一个 chunk 返回
4. 对 PDF 使用相同的 DeepDoc 解析管道

#### 1.4.4 `knowledge_graph`（KG）策略

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 130 行
```python
ParserType.KG.value: naive,
```
**实际映射到 `naive` 策略**（没有独立的 KG 分块逻辑）。

**`naive` 策略**（文件 `/tmp/ragflow/rag/app/naive.py`，第 792 行起的 `chunk()` 函数）：

流程：
1. 支持 docx、pdf、excel、txt、markdown、html 等多种格式
2. **PDF 解析**：通过 `PARSERS` 字典选择解析器（DeepDOC/MinerU/Docling/TCADP/PaddleOCR/PlainText）
3. 文本分割：使用 `delimiter`（默认 `\n!?。；！？`）将文本切分为片段
4. 片段合并：将连续片段合并为 token 数不超过 `chunk_token_num`（默认 128/512）的块
5. 支持自定义子分隔符（`children_delimiter`）
6. 调用 `tokenize_chunks()` 进行分词

**PARSERS 字典**（第 316-324 行）：
```python
PARSERS = {
    "deepdoc": by_deepdoc,
    "mineru": by_mineru,
    "docling": by_docling,
    "opendataloader": by_opendataloader,
    "tcadp parser": by_tcadp,
    "paddleocr": by_paddleocr,
    "plaintext": by_plaintext,
}
```

---

## 2. do_handle_task 函数分析

### 2.1 函数概览

- **文件**：`/tmp/ragflow/rag/svr/task_executor.py`，第 1364-1702 行
- **装饰器**：`@timeout(60 * 60 * 3, 1)` —— 超时时间 3 小时
- **函数签名**：`async def do_handle_task(task)`

### 2.2 主逻辑流程

```
do_handle_task(task)
  │
  ├─ 判断 task_type
  │   ├─ "memory" → handle_save_to_memory_task()
  │   ├─ "dataflow" → run_dataflow()
  │   ├─ "raptor" → 绑定 LLM → run_raptor_for_kb()
  │   ├─ "graphrag" → 绑定 LLM → run_graphrag_for_kb()
  │   ├─ "mindmap" → pass (占位)
  │   └─ 其他（标准分块）→ build_chunks()
  │       │
  │       ├─ 绑定 Embedding 模型（第 1406-1412 行）
  │       ├─ init_kb() 初始化文档存储索引（第 1419 行）
  │       ├─ build_chunks() 解析文档并分块（第 1544 行）
  │       ├─ embedding() 向量化（第 1557 行）
  │       ├─ insert_chunks() 索引写入（第 1585 行）
  │       └─ 可选：auto_keywords / auto_questions / metadata / tagging
  │
  └─ 清理资源、确认 Redis 消息
```

### 2.3 关键技术实现

#### 2.3.1 文档解析与分块（`build_chunks`）

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 268-638 行

1. **获取文件二进制**（第 282-283 行）：从 MinIO/S3 下载文件
2. **选择分块器**（第 279 行）：`chunker = FACTORY[task["parser_id"].lower()]`
3. **合并 KB 解析配置**（第 302 行）：`merge_table_parser_config_from_kb(task)`
4. **执行分块**（第 328-341 行）：通过线程池调用 `chunker.chunk()`
5. **PDF 大纲提取**（第 354-368 行）：如果解析器附加了大纲数据，持久化到文档元数据
6. **图片上传**（第 380-415 行）：将分块中的图片存入 MinIO

#### 2.3.2 向量化（`embedding`）

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 695-745 行

1. 使用 LLMBundle 绑定的 Embedding 模型
2. 标题向量加权（`filename_embd_weight`，默认 0.1）
3. 批处理编码，默认批大小 `settings.EMBEDDING_BATCH_SIZE`
4. 结果存储为 `q_{vector_size}_vec` 字段

```python
async def embedding(docs, mdl, parser_config=None, callback=None):
    ...
    vts, c = await thread_pool_exec(mdl.encode, tts[0:1])
    ...
    vects = title_w * tts + (1 - title_w) * cnts
    for i, d in enumerate(docs):
        v = vects[i].tolist()
        d["q_%d_vec" % len(v)] = v
```

#### 2.3.3 索引写入（`insert_chunks`）

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 1257-1361 行

1. 处理母子块关系（`mom`/`mom_id` 字段）
2. 批量写入文档存储（`docStoreConn.insert`），批大小 `settings.DOC_BULK_SIZE`
3. 更新任务进度（`TaskService.update_chunk_ids`）
4. 取消时支持回滚 RAPTOR 摘要块

#### 2.3.4 可选 LLM 增强功能

`build_chunks` 内部还包含三个可选的 LLM 增强步骤：

1. **Auto Keywords**（第 423-459 行）：使用 Chat LLM 为每个块提取关键词
2. **Auto Questions**（第 461-496 行）：使用 Chat LLM 为每个块生成问题
3. **Metadata Generation**（第 498-562 行）：使用 Chat LLM 提取结构化元数据
4. **Content Tagging**（第 564-631 行）：使用 Chat LLM 对块进行标签分类

这些功能通过 `parser_config` 中的 `auto_keywords`、`auto_questions`、`enable_metadata` 开关控制。

#### 2.3.5 TOC 生成

- 文件：`/tmp/ragflow/rag/svr/task_executor.py`，第 641-686 行（`build_TOC` 函数）

仅在 `parser_id == "naive"` 且 `toc_extraction == True` 时触发（第 1571 行）。
使用 Chat LLM 从分块内容中提取目录结构。

### 2.4 重试与错误处理

- 3 小时超时保护（`@timeout(60 * 60 * 3, 1)`）
- 取消检测（`has_canceled()`）
- 错误回滚机制（取消时删除已插入的块）
- RAPTOR 摘要的检查点恢复

---

## 3. DeepDoc 模块解析器分析

### 3.1 模块结构

DeepDoc 模块的目录结构：

```
deepdoc/
├── __init__.py                  # 模块入口，beartype 类型检查
├── parser/
│   ├── __init__.py              # 解析器注册表
│   ├── pdf_parser.py            # PDF 解析器（核心）
│   ├── docx_parser.py           # DOCX 解析器
│   ├── excel_parser.py          # Excel 解析器
│   ├── ppt_parser.py            # PPT 解析器
│   ├── txt_parser.py            # TXT 解析器
│   ├── html_parser.py           # HTML 解析器
│   ├── json_parser.py           # JSON 解析器
│   ├── markdown_parser.py       # Markdown 解析器
│   ├── epub_parser.py           # EPUB 解析器
│   ├── figure_parser.py         # 图片/图表描述生成器
│   ├── docling_parser.py        # Docling PDF 解析器
│   ├── mineru_parser.py         # MinerU PDF 解析器
│   ├── tcadp_parser.py          # 腾讯云 TCADP 解析器
│   ├── paddleocr_parser.py      # PaddleOCR 解析器
│   ├── opendataloader_parser.py # OpenDataLoader 解析器
│   └── resume/                  # 简历解析子模块
└── vision/
    ├── __init__.py              # 视觉模块注册表
    ├── ocr.py                   # OCR 引擎（PP-OCR）
    ├── layout_recognizer.py     # 布局识别
    ├── recognizer.py            # 基础识别器
    ├── table_structure_recognizer.py  # 表格结构识别
    ├── t_recognizer.py          # 端到端识别器
    ├── t_ocr.py                 # 端到端 OCR
    ├── operators.py             # 图像预处理算子
    └── postprocess.py           # 后处理
```

### 3.2 解析器注册表

- 文件：`/tmp/ragflow/deepdoc/parser/__init__.py`，第 17-41 行

| 导出名称 | 原始类 | 文件 |
|---------|--------|------|
| `PdfParser` | `RAGFlowPdfParser` | `pdf_parser.py` |
| `PlainParser` | `PlainParser` | `pdf_parser.py` |
| `DocxParser` | `RAGFlowDocxParser` | `docx_parser.py` |
| `EpubParser` | `RAGFlowEpubParser` | `epub_parser.py` |
| `ExcelParser` | `RAGFlowExcelParser` | `excel_parser.py` |
| `PptParser` | `RAGFlowPptParser` | `ppt_parser.py` |
| `HtmlParser` | `RAGFlowHtmlParser` | `html_parser.py` |
| `JsonParser` | `RAGFlowJsonParser` | `json_parser.py` |
| `MarkdownParser` | `RAGFlowMarkdownParser` | `markdown_parser.py` |
| `TxtParser` | `RAGFlowTxtParser` | `txt_parser.py` |
| `MarkdownElementExtractor` | `MarkdownElementExtractor` | `markdown_parser.py` |

### 3.3 解析器支持的文件类型

| 解析器 | 支持的文件格式 | 说明 |
|--------|---------------|------|
| `RAGFlowPdfParser` | `.pdf` | 核心 PDF 解析器，支持 OCR + 布局识别 |
| `PlainParser` | `.pdf` | 纯文本 PDF 解析（无 OCR） |
| `RAGFlowDocxParser` | `.docx` | Word 文档解析 |
| `RAGFlowExcelParser` | `.xlsx`, `.xls`, `.csv` | Excel 表格解析 |
| `RAGFlowPptParser` | `.pptx` | PPT 幻灯片解析 |
| `RAGFlowTxtParser` | `.txt`, `.py`, `.js`, `.java`, 等代码文件 | 纯文本解析 |
| `RAGFlowHtmlParser` | `.html`, `.htm` | HTML 解析 |
| `RAGFlowJsonParser` | `.json` | JSON 解析 |
| `RAGFlowMarkdownParser` | `.md`, `.markdown`, `.mdx` | Markdown 解析 |
| `RAGFlowEpubParser` | `.epub` | 电子书解析 |
| `DoclingParser` | `.pdf` | Docling 格式 PDF 解析 |
| `MineruParser` | `.pdf` | MinerU PDF 解析 |
| `TCADPParser` | `.pdf`, `.xlsx`, `.csv` | 腾讯云智能文档解析 |
| `PaddleOCRParser` | `.pdf` | PaddleOCR PDF 解析 |
| `OpenDataLoaderParser` | `.pdf` | OpenDataLoader PDF 解析 |

### 3.4 PDF 解析核心技术

#### 3.4.1 整体流水线

`RAGFlowPdfParser.__call__()`（第 1673-1698 行）：

```python
def __call__(self, fnm, need_image=True, zoomin=3, return_html=False, auto_rotate_tables=None):
    self.outlines = extract_pdf_outlines(fnm)
    self.__images__(fnm, zoomin)          # 1️⃣ 图像渲染 + OCR
    self._layouts_rec(zoomin)              # 2️⃣ 布局分析
    self._table_transformer_job(zoomin, auto_rotate=auto_rotate_tables)  # 3️⃣ 表格结构识别
    self._text_merge()                     # 4️⃣ 文本合并
    self._concat_downward()                # 5️⃣ 垂直合并
    self._filter_forpages()                # 6️⃣ 过滤页眉页脚
    tbls = self._extract_table_figure(need_image, zoomin, return_html, False)  # 7️⃣ 提取表格/图片
    return self.__filterout_scraps(deepcopy(self.boxes), zoomin), tbls
```

#### 3.4.2 第 1 步：图像渲染与 OCR（`__images__`）

- 文件：`/tmp/ragflow/deepdoc/parser/pdf_parser.py`，第 1527-1671 行

**流程**：
1. **PDF 渲染**（第 1538-1541 行）：使用 `pdfplumber` 打开 PDF，将每页渲染为 PIL Image
2. **字符提取**（第 1544 行）：使用 `pdfplumber.page.dedupe_chars().chars` 提取文本字符
3. **乱码检测**（第 1549-1576 行）：
   - PUA/CID 乱码检测（`_is_garbled_text`，阈值 0.3）
   - 字体编码乱码检测（`_is_garbled_by_font_encoding`）
   - 检测到乱码时清空字符列表，强制使用 OCR 路径
4. **语言检测**（第 1584-1591 行）：通过随机采样字符判断是否为英文
5. **OCR 执行**（第 1593-1658 行）：
   - 如果 `self.is_english` 为 True，`chars` 为空（跳过 pdfplumber 文本，直接使用 OCR）
   - 否则优先使用 pdfplumber 文本，OCR 作为补充
   - 支持多 GPU 并行 OCR（`PARALLEL_DEVICES`）
   - 使用 `asyncio` 并发执行

**关键代码**——OCR 预处理（第 1615-1616 行）：
```python
chars = self.page_chars[i] if not self.is_english else []
```
英文文档优先使用 OCR，非英文文档合并 pdfplumber 提取的字符。

**重要特性**（第 1670-1671 行）：
```python
if len(self.boxes) == 0 and zoomin < 9:
    self.__images__(fnm, zoomin * 3, page_from, page_to, callback)
```
如果 OCR 结果为空且缩放倍数 < 9，自动增加分辨率重试。

#### 3.4.3 第 2 步：布局分析（`_layouts_rec`）

- 文件：`/tmp/ragflow/deepdoc/parser/pdf_parser.py`，第 796-802 行

```python
def _layouts_rec(self, ZM, drop=True):
    self.boxes, self.page_layout = self.layouter(self.page_images, self.boxes, ZM, drop=drop)
```

**布局识别器**（`LayoutRecognizer`）：
- 文件：`/tmp/ragflow/deepdoc/vision/layout_recognizer.py`，第 33-150 行
- 支持的布局类型（第 34-46 行）：
  - `_background_`, `Text`, `Title`, `Figure`, `Figure caption`, `Table`, `Table caption`, `Header`, `Footer`, `Reference`, `Equation`
- 垃圾布局（自动过滤）：`footer`, `header`, `reference`
- 可使用两种推理方式：
  1. **ONNX 运行时**（默认）：加载本地 ONNX 模型
  2. **DLA 远程服务**（`DEEPDOC_URL`/`TENSORRT_DLA_SVR` 环境变量）：通过 gRPC 调用远程 DLA 服务

**布局识别器 4 YOLOv10**：

在 `/tmp/ragflow/deepdoc/vision/__init__.py` 第 25 行：
```python
from .layout_recognizer import LayoutRecognizer4YOLOv10 as LayoutRecognizer
```
可见实际使用的是基于 YOLOv10 的布局识别器。

**Ascend 布局识别器**：
支持华为昇腾 NPU 推理，通过 `LAYOUT_RECOGNIZER_TYPE=ascend` 环境变量启用（见 `/tmp/ragflow/deepdoc/parser/pdf_parser.py` 第 76-90 行）。

#### 3.4.4 第 3 步：表格结构识别（`_table_transformer_job`）

- 文件：`/tmp/ragflow/deepdoc/parser/pdf_parser.py`，第 409-555 行

1. 遍历每页的表格布局区域
2. 裁剪表格图像
3. **自动旋转校正**（`auto_rotate` 参数）：评估 0°/90°/180°/270° 四种方向，选择 OCR 置信度最高的方向（`_evaluate_table_orientation()`，第 318-407 行）
4. 使用 `TableStructureRecognizer` 进行表格结构识别
5. 行、列、表头、跨单元格的检测与合并

**表格结构识别器**：
- 文件：`/tmp/ragflow/deepdoc/vision/table_structure_recognizer.py`

#### 3.4.5 OCR 引擎（PP-OCR 架构）

- 文件：`/tmp/ragflow/deepdoc/vision/ocr.py`

`OCR` 类（第 542-587 行）初始化流程：
1. 从 `rag/res/deepdoc` 目录加载 ONNX 模型
2. 如果本地不存在，从 HuggingFace Hub 下载 `InfiniFlow/deepdoc`
3. 每个设备创建一个 `TextDetector` 和 `TextRecognizer` 实例
4. `drop_score = 0.5`（置信度低于 0.5 的识别结果被丢弃）

**`TextDetector`**（第 420-451 行）：
- 基于 DBNet（Differentiable Binarization）的文本检测
- ONNX 模型文件：`det.onnx`
- 图像预处理：限制边长 960px，归一化
- 后处理：DBPostProcess，`unclip_ratio=1.5`

**`TextRecognizer`**（第 139-414 行）：
- 基于 CRNN + CTC 的文本识别
- ONNX 模型文件：`rec.onnx`
- 输入形状：`3, 48, 320`（通道、高度、宽度）
- 字符字典：`ocr.res`
- 批处理大小：16

**OCR 调用**（`OCR.__call__()`，第 708-751 行）：
1. `text_detector` 检测文本区域，返回四边形边界框
2. 对每个边界框进行透视变换校正
3. `text_recognizer` 批量识别文本
4. 过滤置信度低于 `drop_score` 的结果

#### 3.4.6 多 GPU 并行

OCR 支持多 GPU 并行处理（配置项 `settings.PARALLEL_DEVICES`）：
- 每个 GPU 分配独立的 `TextDetector` 和 `TextRecognizer` 实例
- `RAGFlowPdfParser` 使用 `asyncio.Semaphore` 控制并行度（第 73-74 行）
- `__img_ocr_launcher()`（第 1614-1654 行）按 GPU 数量分发 OCR 任务

#### 3.4.7 XGBoost 文本合并模型

- 文件：`/tmp/ragflow/deepdoc/parser/pdf_parser.py`，第 93-102 行

```python
self.updown_cnt_mdl = xgb.Booster()
self.updown_cnt_mdl.set_param({"device": "cpu"})
model_dir = os.path.join(get_project_base_directory(), "rag/res/deepdoc")
self.updown_cnt_mdl.load_model(os.path.join(model_dir, "updown_concat_xgb.model"))
```

用于 `_text_merge()` 中判断上下两个文本块是否应该合并。特征工程在 `_updown_concat_features()`（第 132-175 行）中实现，包含 30+ 维特征（字体、间距、布局类型、标点符号等）。

#### 3.4.8 其他 PDF 解析器

**`by_plaintext`**（`/tmp/ragflow/rag/app/naive.py`，第 296-313 行）：
- 使用 `PlainParser`：不执行 OCR，直接提取 PDF 内置文本
- 或使用 `VisionParser`：通过 VLM 模型对每一页进行视觉理解

**`by_mineru`**（`/tmp/ragflow/rag/app/naive.py`，第 101-161 行）：
- 使用 MinerU 解析引擎
- 需要配置 MinerU 类型的大模型（`LLMType.OCR`）

**`by_docling`**（`/tmp/ragflow/rag/app/naive.py`，第 164-182 行）：
- 使用 Docling 解析引擎
- 支持远程 Docling 服务器模式

**`by_tcadp`**（`/tmp/ragflow/rag/app/naive.py`，第 234-242 行）：
- 腾讯云智能文档解析（需配置 API）

**`by_paddleocr`**（`/tmp/ragflow/rag/app/naive.py`，第 245-293 行）：
- 使用 PaddleOCR 解析引擎（`LLMType.OCR`）
- 注意：这里的 PaddleOCR 是作为 LLM 类型的 OCR 服务，与 DeepDoc 内置的 PP-OCR 实现不同

**`by_opendataloader`**（`/tmp/ragflow/rag/app/naive.py`，第 185-231 行）：
- 使用 OpenDataLoader 解析引擎

### 3.5 视觉模型支持的图片/图表描述

- 文件：`/tmp/ragflow/deepdoc/parser/figure_parser.py`

DeepDoc 支持通过 VLM（Vision Language Model）对 PDF 中的图片和图表生成语义描述，增强检索效果：
- `vision_figure_parser_pdf_wrapper()`：PDF 图表描述
- `vision_figure_parser_docx_wrapper()`：DOCX 图表描述
- `vision_figure_parser_docx_wrapper_naive()`：DOCX 图表描述（naive 模式）

---

## 4. 附录：代码文件索引

| 功能 | 文件路径 | 关键行号 |
|------|---------|---------|
| ParserType 枚举 | `/tmp/ragflow/common/constants.py` | 101-116 |
| 队列命名 | `/tmp/ragflow/common/settings.py` | 136-159 |
| Redis Stream 操作 | `/tmp/ragflow/rag/utils/redis_conn.py` | 397-482 |
| 任务入队（文档） | `/tmp/ragflow/api/db/services/task_service.py` | 456-463 |
| 任务入队（KG/RAPTOR） | `/tmp/ragflow/api/db/services/document_service.py` | 1101 |
| 任务入队（Dataflow） | `/tmp/ragflow/api/db/services/task_service.py` | 552-554 |
| FACTORY 映射 | `/tmp/ragflow/rag/svr/task_executor.py` | 115-132 |
| do_handle_task | `/tmp/ragflow/rag/svr/task_executor.py` | 1364-1702 |
| build_chunks | `/tmp/ragflow/rag/svr/task_executor.py` | 268-638 |
| embedding | `/tmp/ragflow/rag/svr/task_executor.py` | 695-745 |
| insert_chunks | `/tmp/ragflow/rag/svr/task_executor.py` | 1257-1361 |
| paper 分块 | `/tmp/ragflow/rag/app/paper.py` | 149-261 |
| table 分块 | `/tmp/ragflow/rag/app/table.py` | 59-167 |
| one 分块 | `/tmp/ragflow/rag/app/one.py` | 59-167 |
| naive 分块 | `/tmp/ragflow/rag/app/naive.py` | 792-1167+ |
| book 分块 | `/tmp/ragflow/rag/app/book.py` | 63-183 |
| PARSERS 字典 | `/tmp/ragflow/rag/app/naive.py` | 316-324 |
| PDF 解析器主类 | `/tmp/ragflow/deepdoc/parser/pdf_parser.py` | 57-2079 |
| PDF `__call__` | `/tmp/ragflow/deepdoc/parser/pdf_parser.py` | 1673-1698 |
| PDF `__images__` | `/tmp/ragflow/deepdoc/parser/pdf_parser.py` | 1527-1671 |
| PDF `_layouts_rec` | `/tmp/ragflow/deepdoc/parser/pdf_parser.py` | 796-802 |
| PDF `_table_transformer_job` | `/tmp/ragflow/deepdoc/parser/pdf_parser.py` | 409-555 |
| OCR 引擎 | `/tmp/ragflow/deepdoc/vision/ocr.py` | 542-751 |
| TextDetector | `/tmp/ragflow/deepdoc/vision/ocr.py` | 420-451 |
| TextRecognizer | `/tmp/ragflow/deepdoc/vision/ocr.py` | 139-414 |
| 布局识别器 | `/tmp/ragflow/deepdoc/vision/layout_recognizer.py` | 33-150 |
| 表格结构识别器 | `/tmp/ragflow/deepdoc/vision/table_structure_recognizer.py` | - |
| 深度学习模型加载 | `/tmp/ragflow/deepdoc/vision/__init__.py` | 22-26 |
| 解析器注册表 | `/tmp/ragflow/deepdoc/parser/__init__.py` | 17-41 |

---

## 5. 补充分析：源码级细节补充（基于 RAGFlow 最新源码）

### 5.1 parser_id 与任务分页策略

文件：`api/db/services/task_service.py`，第 389-420 行

不同 parser_id 决定了任务拆分的粒度（每个任务处理多少页）：

```python
# task_service.py 第 389-420 行
if doc["parser_id"] == "paper":
    page_size = 22          # paper 模式：每个任务处理 22 页

if doc["parser_id"] in ["one", "knowledge_graph"] or do_layout != "DeepDOC":
    page_size = MAXIMUM_TASK_PAGE_NUMBER   # one/KG：整个文件作为一个任务

# 默认（naive等）：每个任务处理 12 页
```

**设计意图**：
- `paper`：22页一任务，适配学术论文长度，保证章节完整性
- `one`/`knowledge_graph`：整文件一任务，因为需要全局上下文
- `naive` 等：12页一任务，平衡并行度和上下文连贯性
- `table`（Excel）：按 3000 行拆分，不按页

### 5.2 Redis Stream 消息队列完整实现

#### 5.2.1 任务入队（生产者）

文件：`api/db/services/task_service.py`，第 459-463 行

```python
for unfinished_task in unfinished_task_array:
    REDIS_CONN.queue_product(
        settings.get_svr_queue_name(priority, suffix),
        message=unfinished_task
    )
```

文件：`rag/utils/redis_conn.py`，第 397-408 行

```python
def queue_product(self, queue, message) -> bool:
    payload = {"message": json.dumps(message)}
    self.REDIS.xadd(queue, payload)    # Redis Stream XADD 命令
    return True
```

#### 5.2.2 任务消费（消费者）

文件：`rag/utils/redis_conn.py`，第 410-455 行

```python
def queue_consumer(self, queue_name, group_name, consumer_name, msg_id=">"):
    # 创建消费者组（幂等）
    self.REDIS.xgroup_create(queue_name, group_name, id="0", mkstream=True)
    # 读取新消息
    args = {
        "groupname": group_name,
        "consumername": consumer_name,
        "count": 1,           # 每次读取 1 条
        "block": 5,           # 阻塞 5 秒
        "streams": {queue_name: msg_id}
    }
    messages = self.REDIS.xreadgroup(**args)
    return messages
```

#### 5.2.3 消息流转全链路

```
API层创建任务 → task_service 将任务拆分为子任务（按page_size）
    → REDIS_CONN.queue_product() 调用 XADD 推入 Redis Stream
    → Task Executor 消费者循环调用 XREADGROUP 拉取任务
    → handle_task() → collect() → do_handle_task() 执行解析
```

### 5.3 do_handle_task 函数完整分支分析

文件：`rag/svr/task_executor.py`，第 1365 行起

#### 5.3.1 任务类型路由（完整）

```python
# 第 1366-1375 行
if task.get("type") == "memory":
    return handle_save_to_memory_task()     # 记忆存储任务

# 第 1421-1544 行：按 task_type 分支
if task_type == "dataflow":
    run_dataflow(task, progress_callback)   # 数据流管道
elif task_type == "raptor":
    run_raptor_for_kb(task, ...)            # RAPTOR 层次摘要
elif task_type == "graphrag":
    run_graphrag_for_kb(task, ...)          # GraphRAG 知识图谱
elif task_type == "mindmap":
    pass                                     # 思维导图（占位）
else:
    # 默认：标准文档解析分块
    build_chunks(task, progress_callback)
```

#### 5.3.2 标准文档处理流程（默认分支）

```
1. build_chunks(task, callback)
   ├── 从 MinIO 下载文件二进制
   ├── chunker = FACTORY[parser_id]        # 根据parser_id选择分块器
   ├── chunks = chunker.chunk(filename, binary, ...)  # 执行分块
   ├── 上传分块图片到 MinIO
   ├── auto_keywords（可选）：LLM生成关键词
   └── auto_questions（可选）：LLM生成问题

2. embedding(chunks, embedding_model, ...)
   ├── model.encode(chunk_content)          # 编码内容向量
   ├── 标题向量加权混合：
   │   vects = title_w * title_vecs + (1-title_w) * content_vecs
   │   （title_w 默认 0.1）
   └── 存储为 d["q_{dim}_vec"]

3. insert_chunks()
   ├── 批量写入 Elasticsearch/Infinity（批次大小 DOC_BULK_SIZE）
   ├── 记录 chunk_ids 用于取消时回滚
   └── 更新 DocumentService.increment_chunk_num()

4. 后处理（可选）
   ├── TOC 目录提取（naive parser, toc_extraction=True）
   ├── 表格元数据聚合（table parser）
   └── RAPTOR 摘要清理
```

#### 5.3.3 RAPTOR 路径（第 1425-1469 行）

```python
def run_raptor_for_kb(task, ...):
    # 层次聚类摘要
    # 1. 对已有chunks进行GMM聚类
    # 2. 每个聚类用LLM生成摘要
    # 3. 构建摘要树（RAPTOR tree）
    # 4. 摘要节点也写入向量库
```

#### 5.3.4 GraphRAG 路径（第 1473-1535 行）

```python
def run_graphrag_for_kb(task, ...):
    # 知识图谱构建
    # 1. 实体抽取（organization, person, geo, event, category）
    # 2. 实体消歧（entity resolution）
    # 3. 社区检测（community detection）
    # 4. 子图构建（subgraph building）
```

**注意**：knowledge_graph 的 parser_id 在 FACTORY 中映射到 `naive` 分块器，
先做标准分块，然后 task_type="graphrag" 触发 GraphRAG 后处理。

### 5.4 DeepDoc PDF 解析 7 步流程完整代码级分析

文件：`deepdoc/parser/pdf_parser.py`

#### Step 1：页面渲染与OCR（`__images__()`，第 1527 行）

```python
def __images__(self, fnm, zoomin=3, page_from=0, page_to=999):
    # 1. 使用 pdfplumber 打开 PDF
    pdf = pdfplumber.open(fnm)
    # 2. 按 zoomin 倍率渲染页面为图片（默认 72*3=216 DPI）
    # 3. 提取字符级数据：x0, x1, top, bottom, text
    # 4. 乱码检测：检查 PUA/CID 字符比例
    #    - 如果乱码比例高 → 回退到 OCR 模式
    #    - 否则使用 pdfplumber 字符提取
    # 5. 判断语言：英文/中文
```

#### Step 2：布局识别（`_layouts_rec()`，第 796 行）

```python
def _layouts_rec(self, pns, images, ...):
    # 使用 LayoutRecognizer（YOLOv10 ONNX模型）
    # 检测 11 种布局类型：
    # title, text, table, figure, equation,
    # caption, reference, header, footer, list, toc
    # 使用 KMeans 聚类 x 坐标来识别分栏
```

#### Step 3：表格结构识别（`_table_transformer_job()`，第 409 行）

```python
def _table_transformer_job(self, ...):
    # 对布局识别中的 table 区域运行 TableStructureRecognizer
    # 识别表格内部结构：行、列、单元格
    # 输出 HTML 格式的表格
```

#### Step 4：文本合并（`_text_merge()`，第 888 行）

```python
def _text_merge(self, boxes, ...):
    # 1. 水平合并：相邻的同类型布局框横向拼接
    # 2. 垂直合并决策：使用 XGBoost 模型
    #    特征包括（30+个）：
    #    - y 方向距离
    #    - 文本结尾模式（句号/逗号/无标点）
    #    - 布局类型是否匹配
    #    - token 重叠度
    #    - 字号比例
    #    - 是否跨栏/跨页
```

#### Step 5：表格/图片提取（`_extract_table_figure()`，第 1206 行）

```python
def _extract_table_figure(self, ...):
    # 1. 从文本框中分离 table 和 figure 区域
    # 2. 合并跨页表格
    # 3. 提取 caption（标题说明）
    # 4. 将 caption 关联到最近的 table/figure
    # 5. 表格通过 TableStructureRecognizer 转为 HTML
```

#### Step 6：纵向拼接（`_concat_downward()`，第 1030 行）

```python
def _concat_downward(self, ...):
    # 使用 XGBoost 模型预测是否应该纵向合并
    # 处理跨页文本连续性
    # 特征：垂直距离、字体大小、布局类型等
```

#### Step 7：页眉页脚过滤（`_filter_forpages()`，第 1134 行）

```python
def _filter_forpages(self, ...):
    # 1. 移除页眉页脚（通常在页面顶部/底部的重复文本）
    # 2. 过滤噪声字符（乱码、水印残留等）
```

### 5.5 补充解析器一览

除 paper/table/one/naive/knowledge_graph 外，RAGFlow 还支持以下解析策略：

| parser_id | 映射函数 | 说明 |
|-----------|---------|------|
| book | `rag.app.book.chunk()` | 书籍解析，按章节分块，支持目录提取 |
| laws | `rag.app.laws.chunk()` | 法律法规文档，按条款分块 |
| presentation | `rag.app.presentation.chunk()` | PPT演示文稿，按幻灯片分块 |
| resume | `rag.app.resume.chunk()` | 简历文档，结构化字段提取 |
| qa | `rag.app.qa.chunk()` | 问答对格式，保留Q-A对应关系 |
| email | `rag.app.email.chunk()` | 邮件格式，按邮件分块 |
| audio | `rag.app.audio.chunk()` | 音频文件，ASR转写后分块 |
| picture | `rag.app.picture.chunk()` | 图片文件，OCR/视觉模型描述 |
| tag | `rag.app.tag.chunk()` | 标签分类 |
| manual | `rag.app.manual.chunk()` | 手册/说明书 |

### 5.6 ParserType 完整枚举

文件：`common/constants.py`，第 101-116 行

```python
class ParserType(Enum):
    PAPER = "paper"                    # 学术论文
    TABLE = "table"                    # 表格/Excel
    ONE = "one"                        # 整文件=单块
    KG = "knowledge_graph"             # 知识图谱（映射到naive）
    NAIVE = "naive"                    # 默认分隔符分块
    BOOK = "book"                      # 书籍
    LAWS = "laws"                      # 法律法规
    MANUAL = "manual"                  # 手册
    QA = "qa"                          # 问答对
    PRESENTATION = "presentation"      # PPT
    RESUME = "resume"                  # 简历
    PICTURE = "picture"                # 图片
    AUDIO = "audio"                    # 音频
    EMAIL = "email"                    # 邮件
    TAG = "tag"                        # 标签
```

### 5.7 PDF 解析器注册表（PARSERS）

文件：`rag/app/naive.py`，第 338-346 行

除了 DeepDoc 内置解析器，RAGFlow 支持多种第三方 PDF 解析器：

```python
PARSERS = {
    "deepdoc":       by_deepdoc,        # 内置：OCR + 布局识别
    "mineru":        by_mineru,         # MinerU 外部解析器
    "docling":       by_docling,        # IBM Docling
    "opendataloader": by_opendataloader, # OpenDataLoader
    "tcadp parser":  by_tcadp,          # 腾讯云 API
    "paddleocr":     by_paddleocr,      # PaddleOCR
    "plaintext":     by_plaintext,      # 纯文本 / Vision LLM
}
```

**选择方式**：用户在 RAGFlow 界面创建知识库时可选择 `layout_recognize` 参数，
决定使用哪个 PDF 解析器。默认为 `"DeepDOC"`。

---

## 6. 工单验收对照检查表

| 验收项 | 对应章节 | 状态 |
|--------|---------|------|
| paper/table/one/KG 分块策略 | 1.3, 1.4, 5.1 | ✓ |
| Redis Stream 消息队列机制 | 1.2, 5.2 | ✓ |
| do_handle_task 主要逻辑 | 2.1-2.3, 5.3 | ✓ |
| DeepDoc 内置解析器 | 3.2, 5.5 | ✓ |
| 支持的文件类型 | 3.3, 5.5, 5.6 | ✓ |
| PDF 解析技术 | 3.4, 5.4 | ✓ |
