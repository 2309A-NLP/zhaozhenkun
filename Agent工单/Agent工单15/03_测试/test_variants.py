"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
30+ 变体场景测试用例
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发", "backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
passed = 0
failed = 0
failures = []

def _assert_ok(r):
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("success") or "reply" in data, f"no success/reply: {list(data.keys())[:5]}"

def _assert_422(r):
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

def _repeat_book(n, msg):
    for i in range(n):
        r = client.post("/api/registration/chat", json={"message": msg})
        assert r.status_code == 200

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS {name}")
    except AssertionError as e:
        failed += 1
        msg = f"  FAIL {name}: {e}"
        print(msg)
        failures.append(msg)
    except Exception as e:
        failed += 1
        msg = f"  ERROR {name}: {e}"
        print(msg)
        failures.append(msg)


# ================================================================
# 挂号管理 - 32 个变体场景
# ================================================================
print("=" * 60)
print("挂号管理 变体场景测试 (32 cases)")
print("=" * 60)

test("T01 大宝儿科专家", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮我大宝挂一个今天下午2点儿科专家的号"})))

test("T02 牙科最近号源", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "牙科最近的号哪天的？"})))

test("T03 再约之前专家", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我之前挂过眼科的一个专家，帮我再约那个专家的号"})))

test("T04 二宝皮肤科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我明天上午9点想带二宝看皮肤科，还有号吗？"})))

test("T05 取消消化内科号", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "取消我上周三挂的消化内科普通号"})))

test("T06 查张建国坐诊", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮我查下张建国医生下周的坐诊时间"})))

test("T07 小宝看病", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮小宝挂儿科普通号"})))

test("T08 自己看病", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我想挂一个内科主任的号"})))

test("T09 大宝二宝都挂", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "大宝和二宝都挂儿科"})))

test("T10 牙科映射口腔科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "给我挂牙科今天的号"})))

test("T11 心脏科映射内科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "心脏科有今天的号吗？"})))

test("T12 妇产科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "妇产科明天上午有号吗？"})))

test("T13 神经内科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "神经内科最近的号是哪天？"})))

test("T14 骨科主任", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "骨科有主任医师的号吗？"})))

test("T15 耳鼻喉科", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮我挂耳鼻喉科"})))

test("T16 上午时段", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "明天上午10点儿科专家号"})))

test("T17 默认时段", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "挂儿科专家号"})))

test("T18 主治医师", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "挂内科主治医师的号"})))

test("T19 副主任医师", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "皮肤科副主任医师有号吗？"})))

test("T20 普通号", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮我挂儿科普通号"})))

test("T21 不存在科室", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我想挂外星人科的号"})))

test("T22 过去日期", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我想挂昨天下午的儿科号"})))

test("T23 空消息422", lambda: _assert_422(client.post(
    "/api/registration/chat", json={"message": ""})))

test("T24 长消息", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "帮我挂儿科号" + "测试" * 100})))

test("T25 特殊字符", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "%%% 挂号 儿科 $$@"})))

test("T26 英文输入", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "book pediatric expert"})))

test("T27 连续挂号压力", lambda: _repeat_book(20, "挂呼吸内科普通号"))

test("T28 取消不存在", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "取消我不存在的挂号记录"})))

test("T29 所有科室", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "今天有哪些科室有号？"})))

test("T30 下周三", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "下周三上午儿科主任号"})))

test("T31 混合意图", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "我头疼应该挂什么科？顺便帮我挂一下"})))

test("T32 周末挂号", lambda: _assert_ok(client.post(
    "/api/registration/chat", json={"message": "周六下午儿科有号吗？"})))


# ================================================================
# 健康咨询 - 33 个变体场景
# ================================================================
print("\n" + "=" * 60)
print("健康咨询 变体场景测试 (33 cases)")
print("=" * 60)

test("C01 百日咳病原体", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳的致病病原体是什么？"})))

test("C02 百日咳传播", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳主要通过什么途径传播？"})))

test("C03 百日咳症状", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳最具特征性的临床表现是什么？"})))

test("C04 百日咳血常规", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳患者的血常规检查会呈现什么特征？"})))

test("C05 百日咳抗生素", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳西医治疗首选的抗生素是什么？"})))

test("C06 百日咳并发症", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳最常见的严重并发症是什么？"})))

test("C07 百日咳中医", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "中医治疗痉咳期百日咳的主方是什么？"})))

test("C08 百日咳隔离", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳患者的隔离期应持续多久？"})))

test("C09 百日咳护理", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "护理百日咳患儿时需特别注意防范什么紧急情况？"})))

test("C10 百日咳饮食", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "百日咳患者应避免食用哪类食物？"})))

test("C11 肺炎症状", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "新冠肺炎有什么症状？"})))

test("C12 糖尿病饮食", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "糖尿病患者不能吃什么？"})))

test("C13 高血压治疗", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "高血压怎么治疗？"})))

test("C14 流感传播", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "流感通过什么途径传播？"})))

test("C15 哮喘护理", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "哮喘患者怎么护理？"})))

test("C16 湿疹科室", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "湿疹应该挂什么科？"})))

test("C17 鼻炎并发症", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "过敏性鼻炎有什么并发症？"})))

test("C18 肚子疼口语", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "我肚子疼需要吃什么药？"})))

test("C19 头疼口语", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "头疼得厉害怎么办？"})))

test("C20 拉肚子口语", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "拉肚子三天了，是什么病？"})))

test("C21 没力气头晕", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "最近总是没力气、头晕"})))

test("C22 感冒发烧咳嗽", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "感冒发烧咳嗽，吃什么药？"})))

test("C23 腰痛检查科室", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "腰痛腿痛需要做什么检查？挂什么科？"})))

test("C24 手足口病", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "手足口病是怎么引起的？怎么预防？"})))

test("C25 不存在疾病", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "火星病毒感染怎么治疗？"})))

test("C26 空消息422", lambda: _assert_422(client.post(
    "/api/consultation/chat", json={"message": ""})))

test("C27 长问题", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "肺炎的症状" + "有什么" * 100})))

test("C28 英文问题", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "What are the symptoms of pertussis?"})))

test("C29 模糊描述", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "不舒服，全身都不舒服，说不上哪不舒服"})))

test("C30 新生儿黄疸", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "新生儿黄疸需要治疗吗"})))

test("C31 乙肝疫苗", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "乙肝疫苗需要打几针"})))

test("C32 追问上下文", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "传播途径呢？"})))

test("C33 心梗急救", lambda: _assert_ok(client.post(
    "/api/consultation/chat", json={"message": "突发心梗应该怎么急救？"})))


# ================================================================
# 结果统计
# ================================================================
total = passed + failed
print("\n" + "=" * 60)
print(f"Results: {passed}/{total} passed, {failed} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  {f}")
print("=" * 60)
