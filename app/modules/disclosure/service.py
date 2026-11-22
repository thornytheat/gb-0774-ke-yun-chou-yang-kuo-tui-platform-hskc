from app.config import DISCLOSURE, SUPPRESS_SINGLE

# 公开裁定规则（DISCLOSURE 规则版本）：
# 1. 全市各选项扩推人数照原数公开，供调度直接使用；
# 2. 仅当分层内只有一份有效答卷（usable == 1）时抑制该层明细，避免全市数减其余分层反推单份答案；
# 3. 抑制层保留层名、出票人口、有效份数与状态作为线路参考，隐去一切可反推答案的明细；
# 4. 零响应层与多答卷层一律公开。


def _public_layer(name, weighted, allocated, balance_row):
    return dict(
        name=name, status='public', reason=None,
        population=allocated['population'], usable=weighted['usable'],
        layer_status=weighted['status'], unknown=allocated['unobserved'],
        integers=dict(allocated['integers']),
        quotas=dict(weighted['quotas']),
        factor=weighted['factor'],
        observed=dict(weighted['observed']),
        bias=dict(balance_row['bias']),
    )


def _suppressed_layer(name, weighted, allocated):
    return dict(
        name=name, status='suppressed', reason=SUPPRESS_SINGLE,
        population=allocated['population'], usable=weighted['usable'],
        layer_status=weighted['status'],
        reference=dict(population=allocated['population'], layer=weighted['status']),
    )


def adjudicate(frame, weighted, allocation, balance):
    strata = []
    suppressed, public = [], []
    for name in frame['population']:
        weighted_row = weighted['layers'][name]
        allocated_row = allocation['layers'][name]
        balance_row = balance['strata'][name]
        if weighted_row['usable'] == 1:
            view = _suppressed_layer(name, weighted_row, allocated_row)
            suppressed.append(name)
        else:
            view = _public_layer(name, weighted_row, allocated_row, balance_row)
            public.append(name)
        strata.append(view)
    city = dict(
        integers=dict(allocation['totals']),
        estimated=allocation['estimated'],
        unknown=allocation['unknown'],
        population=balance['population'],
        bias=dict(balance['bias']),
    )
    return dict(
        rule=DISCLOSURE,
        city=city,
        strata=strata,
        public_layers=public,
        suppressed_layers=suppressed,
        suppression_reasons={SUPPRESS_SINGLE: list(suppressed)},
    )
