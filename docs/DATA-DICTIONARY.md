# 抽样扩推数据字典

| 原件 | 字段 | 定义 |
|---|---|---|
| returns.csv | ticket, trip, reported_layer | 文本票号、文本班次、原申报层。保留前导零 |
| returns.csv | visit, status | 正整数重访版次、YES 有效候选或 NO 未回应 |
| returns.csv | probability, choice | 抽中概率，支持十进制或分数且大于 0 不超过 1。问项 direct/transfer/other |
| frame.csv | trip, revision, layer, tickets | 文本班次、正整数版次、当前层名、非负整数出票量 |

UTF-8 文本允许 BOM 及重复表头，表头字段可重新排列。每条记录保留最后一物理行号；重复表头和空行单独统计。空串、`-`、`N/A`、`NULL`、`未知` 为缺项。结构性错误的出票表拒绝生成归档。每份输入上限 350 KB。

同票号按最大的 visit 裁决，同最高版录入一致保留最早行，矛盾的同版行全部隔离。最新不回应也会替换旧答卷。班次选最高 revision，历史层合法的答卷统一改到该班次当前层。出票同版冲突停止发布，完全相同的版本行保留全部出处，只计一个基数。

基础权为 1/抽中概率。层内以出票人口除以基础权总和得到校准因子，乘逐票基础权。零有效回应的正基数层保留全部不可推断人口，有效回收但零出票的层保留采信证据与零扩推值。所有概率、校准配额与份额以精确分数字符串存储。

每层整数配额先取底，再依余数从大到小补足。并列按直达、换乘、其他顺序。全局扩推人数相加各层整数。全局偏差按已校准分层的问项原始份额与整数报告份额相减，以百分点表示。零分母用 `null`。

归档包含输入 SHA-256、规则版本、UTC 生成时间、耗时毫秒和结果摘要。签发摘要用于内容完整性复核。此样例计算设计权重与人口总数，未估计置信区间或抽样方差。

## 公开裁定与签发

公开裁定阶段（规则版本 `disclosure-2026.1`）在偏差对账后对每个当前分层给出口径：层内有效答卷 `usable == 1` 判为 `suppressed`（原因 `SINGLE_QUESTIONNAIRE`），其余分层（含零响应层）判为 `public`。

- 全市 `city.integers`（直达/换乘/其他）、`estimated`、`unknown` 与全局偏差照原数公开。
- 抑制层只输出 `name`、`population`、`usable`、`layer_status` 与 `reference`，隐去 `integers`、`quotas`、`factor`、`observed`、`bias` 等可由全市数减其余分层反推单份答案的明细；层名与出票人口保留作线路参考。
- 公开层输出各问项整数人数、精确配额、校准因子、观测计数与层内偏差。

公开签发件（`GET /api/export/<id>`）只含 `manifest`（含 `version` 与 `disclosure` 规则版本、原件与结果摘要）、`disclosure`、`excluded` 隔离计数、`seal` 与 `issuance`，**不含原始答卷和完整结果**；原件仍写入内部归档 `originals` 表供复核，内部 `authenticate` 校验失败（`BAD_SEAL`/`UNBALANCED`）不予签发。签发页与下载件共用同一 `build_publication`，印章为公开包规范化 JSON 的 SHA-256，确定性可复算。

`issuances` 表以批次 id 为主键记录印章、裁定规则、SPEC 与 UTC 签发时间：同批重复领取或先复算再领取都只保留一条（`INSERT OR IGNORE`），印章不变。晚到回访改变原件后输入哈希变化，生成新批次 id 并重算公开范围；旧批次行与其签发记录原样保留，旧公开包仍可凭自身印章核验。
