# 挂号管理系统 - ER 图 & 业务流程图

**工单编号：** 人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1

---

## 1. 实体关系图 (ER Diagram)

```mermaid
erDiagram
    users ||--o{ children : "有多个孩子"
    users ||--o{ appointments : "发起挂号"
    children ||--o{ appointments : "就诊人"
    departments ||--o{ doctors : "包含"
    doctors ||--o{ schedules : "排班"
    doctors ||--o{ appointments : "被预约"
    schedules ||--o{ appointments : "对应号源"

    users {
        INTEGER id PK "用户ID"
        TEXT name "姓名"
        TEXT phone "电话"
        TEXT created_at "创建时间"
    }

    children {
        INTEGER id PK "孩子ID"
        INTEGER user_id FK "关联用户"
        TEXT name "姓名"
        INTEGER age "年龄"
        TEXT gender "性别"
    }

    departments {
        INTEGER id PK "科室ID"
        TEXT name UK "科室名称"
        TEXT description "科室描述"
    }

    doctors {
        INTEGER id PK "医生ID"
        TEXT name "姓名"
        INTEGER department_id FK "所属科室"
        TEXT title "职称"
        TEXT description "简介"
    }

    schedules {
        INTEGER id PK "排班ID"
        INTEGER doctor_id FK "医生"
        TEXT date "日期(YYYY-MM-DD)"
        TEXT time_slot "时段(上午/下午)"
        INTEGER max_patients "最大接诊量"
        INTEGER current_patients "已挂号人数"
    }

    appointments {
        INTEGER id PK "预约ID"
        INTEGER user_id FK "用户"
        INTEGER child_id FK "就诊孩子"
        INTEGER doctor_id FK "医生"
        INTEGER schedule_id FK "排班"
        TEXT status "状态(confirmed/cancelled/completed)"
        TEXT created_at "创建时间"
    }
```

## 2. 挂号业务流程图

### 2.1 挂号流程 (Book Appointment)

```mermaid
flowchart TD
    A[用户输入自然语言] --> B[DeepSeek 意图解析]
    B --> C{意图识别}
    C -->|book| D[提取参数: 科室/级别/时间/就诊人]
    D --> E[科室口语→正式名映射]
    E --> F[医生级别口语→数据库值]
    F --> G[查询号源: schedules 表]
    G --> H{有可用号源?}
    H -->|有| I[号源计数+1]
    I --> J[插入预约记录 appointments]
    J --> K[返回成功: 科室+医生+时间]
    H -->|无精确匹配| L[放宽条件: 同科室最近号源]
    L --> M{有替代号源?}
    M -->|有| N[推荐替代号源 + 询问用户]
    M -->|无| O[返回: 暂无可挂号源]
    C -->|unknown| P[规则降级: 关键词匹配]
    P --> D
```

### 2.2 号源查询流程 (Query)

```mermaid
flowchart TD
    A[用户查询] --> B[提取科室参数]
    B --> C[口语映射]
    C --> D{指定科室?}
    D -->|是| E[按科室过滤 schedules]
    D -->|否| F[展示全部科室号源]
    E --> G[关联 doctors + departments]
    F --> G
    G --> H[计算剩余号源: max - current]
    H --> I[排序: 日期升序]
    I --> J[返回前8条]
```

### 2.3 取消挂号流程 (Cancel)

```mermaid
flowchart TD
    A[用户取消请求] --> B[解析: 科室/级别]
    B --> C[查找用户待取消预约]
    C --> D{精确匹配?}
    D -->|有| E[UPDATE status = 'cancelled']
    E --> F[返回: 已取消信息]
    D -->|无| G[取最新一条预约取消]
    G --> F
    C -->|无任何预约| H[返回: 无预约记录]
```

### 2.4 医生查询流程 (Doctor Query)

```mermaid
flowchart TD
    A[用户查询医生] --> B[模糊匹配医生姓名]
    B --> C[JOIN departments + schedules]
    C --> D{找到?}
    D -->|是| E[展示: 姓名/职称/科室/排班]
    D -->|否| F[返回: 未找到]
```

## 3. Neo4j 知识图谱图模型

```mermaid
graph TD
    Disease[疾病 Disease] -->|HAS_SYMPTOM| Symptom[症状 Symptom]
    Disease -->|TREATED_WITH| Drug[药物 Drug]
    Disease -->|BELONGS_TO| Department[科室 Department]
    Disease -->|HAS_COMPLICATION| Complication[并发症 Complication]
    Disease -->|CAUSED_BY| Pathogen[病原体 Pathogen]
    Disease -->|TRANSMITTED_BY| Transmission[传播途径 Transmission]
    Disease -->|PREVENTED_BY| Prevention[预防措施 Prevention]
    Disease -->|NEEDS_NURSING| Nursing[护理要点 Nursing]
    Disease -->|CAN_EAT| Food[宜吃食物 Food]
    Disease -->|AVOID_EAT| Food2[忌吃食物 Food]
    Disease -->|DIAGNOSED_BY| Diagnosis[诊断方法 Diagnosis]
```

## 4. 数据库表关系说明

| 关系 | 类型 | 说明 |
|------|------|------|
| users → children | 1:N | 一个用户可有多个孩子 |
| users → appointments | 1:N | 一个用户可多次挂号 |
| departments → doctors | 1:N | 一个科室有多位医生 |
| doctors → schedules | 1:N | 一个医生有多个排班时段 |
| schedules → appointments | 1:N | 一个号源对应多个预约(最多max_patients个) |
| doctors → appointments | 1:N | 一个医生被多次预约 |
