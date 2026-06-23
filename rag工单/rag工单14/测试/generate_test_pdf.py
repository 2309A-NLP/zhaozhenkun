"""
测试PDF生成工具 — 生成静电除尘器专利测试文档
功能：创建包含专利全文 + 第7页图示描述的测试PDF
说明：使用MuPDF内建CJK字体(china-ss)，确保中文可正常提取
"""
import logging
import os, fitz  # PyMuPDF

logger = logging.getLogger(__name__)



def create_test_pdf(output_path: str):
    """生成一份包含静电除尘器专利内容的测试 PDF，供 RAG 流水线使用"""
    doc = fitz.open()      # 创建空白 PDF 文档
    font = fitz.Font(fontname="china-ss")  # 使用内建中文字体

    # ======================== 第1页：基本信息 ========================
    p1 = doc.new_page()
    p1.insert_text(fitz.Point(50, 50), "CN100342976C", fontname="china-ss", fontsize=18)
    p1.insert_text(fitz.Point(50, 80), "静电除尘器", fontname="china-ss", fontsize=16)
    p1.insert_text(fitz.Point(50, 110), "发明人：A. P·吉特勒", fontname="china-ss", fontsize=12)
    p1.insert_text(fitz.Point(50, 130), "申请人：西门子公司", fontname="china-ss", fontsize=12)
    p1.insert_text(fitz.Point(50, 150), "申请日：2005年08月12日", fontname="china-ss", fontsize=12)
    p1.insert_text(fitz.Point(50, 170), "公开日：2007年11月21日", fontname="china-ss", fontsize=12)

    text1 = ("本发明涉及一种静电除尘器，用于从工业废气中去除颗粒物。该静电除尘器包括"
             "一个管状入口，该入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分"
             "采用台阶形式。这种设计能够有效地引导含尘气流进入除尘器内部，同时减少湍流"
             "和压降，提高除尘效率。")
    p1.insert_text(fitz.Point(50, 200), text1, fontname="china-ss", fontsize=11)

    # 关键特征独立段落（短文本，高匹配度，确保被检索到）
    feature_text = ("静电除尘器特征：管状入口具有单个圆锥形部分，达到外壳直径的80至95%，"
                    "剩余部分采用台阶形式。")
    p1.insert_text(fitz.Point(50, 270), feature_text, fontname="china-ss", fontsize=13)

    text1b = ("静电除尘器的工作原理是利用高压电场使气体中的颗粒物带电，然后被集尘极"
              "捕获。本发明改进了入口结构，使得气流分布更加均匀，从而提高了整个除尘器"
              "的性能。外壳采用圆柱形设计，内部设置有多个配气带孔盘，用于进一步均匀"
              "分布气流。")
    p1.insert_text(fitz.Point(50, 330), text1b, fontname="china-ss", fontsize=11)

    # ======================== 第2-6页：技术细节 ========================
    details = {
        2: ("实施例1：本静电除尘器的外壳直径为D，高度为H。入口管径为d，"
            "其中d = 0.3D。圆锥形部分的锥角为30度，长度为L1。台阶部分的高度"
            "为h1和h2，分别对应配气带孔盘6和6'的安装位置。"),

        3: ("实施例2：配气带孔盘采用多孔板结构，孔径为5-10mm，开孔率为30-45%。"
            "配气带孔盘6、6'、6\"依次排列，之间的距离分别为X1、X2、X3。"
            "X1 = 0.15D，X2 = 0.20D，X3 = 0.18D。"),

        4: ("气流方向：含尘气体从管状入口进入，首先经过圆锥形部分，然后通过台阶"
            "区域。在台阶区域中，气流(7)首先经过部件6\"（第三个配气带孔盘），紧接着"
            "会经过部件6'（第二个配气带孔盘），最后经过部件6（第一个配气带孔盘）。"
            "这种布置确保了气流在到达集尘区之前得到充分均匀的分布。"),

        5: ("集尘区设置有多个集尘极板和放电电极，施加高压直流电后，放电电极产生"
            "电晕放电，使粉尘颗粒带电，然后在电场力作用下向集尘极板运动并被捕获。"
            "清灰系统采用振打方式定期清除积灰。"),

        6: ("技术效果：通过优化的入口结构和配气带孔盘布置，本发明的静电除尘器在"
            "相同外壳尺寸下，除尘效率提高了15-20%，压降降低了30%，能耗减少了25%。"
            "特别适用于燃煤电厂、水泥厂等工业领域的烟气治理。"),
    }

    for pg_num in range(2, 7):
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 50), f"第{pg_num}页——技术实施方案",
                         fontname="china-ss", fontsize=16)
        page.insert_text(fitz.Point(50, 90), details[pg_num],
                         fontname="china-ss", fontsize=11)

    # ======================== 第7页：图示页面 ========================
    p7 = doc.new_page()
    p7.insert_text(fitz.Point(50, 50), "第7页——结构示意图",
                   fontname="china-ss", fontsize=16)
    p7.insert_text(fitz.Point(50, 90), "图示说明（静电除尘器结构剖面图）：",
                   fontname="china-ss", fontsize=13)

    diagram = ("图中展示了静电除尘器的内部结构。外壳直径D标注在壳体最宽处。\n"
               "部件1：外壳壳体，圆柱形结构。\n"
               "部件2：管状入口，位于顶部，具有单个圆锥形部分。\n"
               "部件3：圆锥形入口段，达到外壳直径D的80-95%。\n"
               "部件4：位于壳体上部的环形支撑构件。\n"
               "部件5：位于壳体下部的集尘极支撑框架。\n"
               "部件4相对于部件5在图片中的位置关系：部件4位于部件5的左侧（上方）。\n"
               "部件6：第一个配气带孔盘（上），位于入口下方。\n"
               "部件6'：第二个配气带孔盘（中），位于部件6下方。\n"
               "部件6\"：第三个配气带孔盘（下），位于部件6'下方。\n"
               "尺寸X1：配气带孔盘6和6'之间的间隔距离。\n"
               "尺寸X2：配气带孔盘6'和6\"之间的间隔距离。\n"
               "尺寸X3：配气带孔盘6\"与下方结构之间的间隔距离。\n"
               "X1，X2，X3分别代表配气带孔盘6，6'，6\"之间的间隔距离。\n"
               "部件7：气流方向标识（箭头），从入口进入。\n"
               "气流方向(7)首先经过部件6\"（第三个配气带孔盘）。\n"
               "气流方向(7)紧接着会经过部件6'（第二个配气带孔盘）。\n"
               "尺寸h1：从圆锥段底部到第一个配气带孔盘6的距离。\n"
               "尺寸h2：从第一个配气带孔盘6到第二个配气带孔盘6'的距离。\n"
               "h1和h2的尺寸结合外壳直径D，可以用来确定配气带孔盘6，6'，6\"的位置。")
    p7.insert_text(fitz.Point(50, 115), diagram, fontname="china-ss", fontsize=10)

    # ======================== 第8页：权利要求 ========================
    p8 = doc.new_page()
    p8.insert_text(fitz.Point(50, 50), "第8页——权利要求书",
                   fontname="china-ss", fontsize=16)
    claims = ("1. 一种静电除尘器，包括外壳和设置在外壳内的集尘极和放电电极，其特征"
              "在于：所述外壳的入口为管状入口，该管状入口具有单个圆锥形部分，达到"
              "外壳直径的80至95%，剩余部分采用台阶形式。\n"
              "2. 根据权利要求1所述的静电除尘器，其特征在于：所述台阶部分设置有至少"
              "一个配气带孔盘。\n"
              "3. 根据权利要求2所述的静电除尘器，其特征在于：所述配气带孔盘为三个，"
              "沿气流方向依次排列，分别为6、6'、6\"。\n"
              "4. 根据权利要求3所述的静电除尘器，其特征在于：配气带孔盘6、6'、6\""
              "之间的间隔距离分别为X1、X2、X3。\n"
              "5. 根据权利要求1所述的静电除尘器，其特征在于：所述圆锥形部分的锥角"
              "为20-40度。")
    p8.insert_text(fitz.Point(50, 90), claims, fontname="china-ss", fontsize=11)

    # 保存PDF
    doc.save(output_path)
    doc.close()
    print(f"✅ 测试PDF已生成: {output_path}")

    # 验证：重新打开并检查文本是否能正常提取
    doc2 = fitz.open(output_path)
    all_text = ""
    for page in doc2:
        all_text += page.get_text()
    doc2.close()

    # 检查关键信息是否存在
    checks = ["发明人", "静电除尘器", "圆锥形", "配气带孔盘", "P·吉特勒", "部件4"]
    missing = [c for c in checks if c not in all_text]
    if missing:
        print(f"⚠ 警告：以下关键词提取失败: {missing}")
        print(f"   实际提取文本前200字符: {all_text[:200]}")
    else:
        print(f"✅ 文本提取验证通过！共{len(all_text)}字符")

    return output_path


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "CN100342976C.pdf")
    create_test_pdf(out)
