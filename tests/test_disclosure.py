from app.modules.disclosure.service import adjudicate
from app.pipeline import run


def _tables(*rows):
    returns = 'ticket,trip,reported_layer,visit,status,probability,choice\n' + '\n'.join(rows)
    frame = ('trip,revision,layer,tickets\n'
             'T1,1,枢纽,60\nT2,1,城北,30\nT3,1,末班,10\n')
    return {'returns': returns, 'frame': frame}


def _answer(ticket, trip, layer, choice, probability='1/2', visit=1, status='YES'):
    return f'{ticket},{trip},{layer},{visit},{status},{probability},{choice}'


def test_city_totals_are_kept_verbatim():
    tables = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T1', '枢纽', 'transfer'),
        _answer('3', 'T2', '城北', 'other'),
        _answer('4', 'T2', '城北', 'direct'),
        _answer('5', 'T2', '城北', 'transfer'),
        _answer('6', 'T3', '末班', 'direct'),
    )
    disclosure = run(tables)['disclosure']
    allocation = run(tables)['allocation']
    assert disclosure['city']['integers'] == allocation['totals']
    assert disclosure['city']['estimated'] == allocation['estimated']


def test_single_questionnaire_layer_is_suppressed_others_public():
    tables = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T1', '枢纽', 'transfer'),
        _answer('3', 'T2', '城北', 'other'),
        _answer('4', 'T2', '城北', 'direct'),
        _answer('5', 'T3', '末班', 'direct'),
    )
    disclosure = run(tables)['disclosure']
    by_name = {row['name']: row for row in disclosure['strata']}
    assert disclosure['suppressed_layers'] == ['末班']
    assert set(disclosure['public_layers']) == {'枢纽', '城北'}
    single = by_name['末班']
    assert single['status'] == 'suppressed' and single['reason'] == 'SINGLE_QUESTIONNAIRE'
    assert 'integers' not in single and 'quotas' not in single and 'observed' not in single
    # 线路参考保留
    assert single['population'] == 10 and single['usable'] == 1
    assert single['reference'] == {'population': 10, 'layer': 'calibrated'}
    public = by_name['枢纽']
    assert public['status'] == 'public' and public['integers']


def test_suppression_blocks_subtraction_but_keeps_city_total():
    tables = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T1', '枢纽', 'transfer'),
        _answer('3', 'T2', '城北', 'direct'),
        _answer('4', 'T3', '末班', 'other'),
    )
    result = run(tables)
    disclosure = result['disclosure']
    # 全市原数仍在
    assert disclosure['city']['integers'] == result['allocation']['totals']
    # 单答卷层选项明细不可从公开包取得
    single = next(row for row in disclosure['strata'] if row['name'] == '末班')
    assert set(single) >= {'name', 'status', 'reason', 'population', 'usable', 'layer_status', 'reference'}
    assert not {'integers', 'quotas', 'observed', 'bias'} & set(single)


def test_zero_response_layer_is_public_without_suppression():
    tables = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T1', '枢纽', 'transfer'),
        _answer('3', 'T2', '城北', 'other'),
        _answer('4', 'T2', '城北', 'direct'),
    )
    disclosure = run(tables)['disclosure']
    by_name = {row['name']: row for row in disclosure['strata']}
    assert by_name['末班']['status'] == 'public'
    assert by_name['末班']['usable'] == 0 and by_name['末班']['unknown'] == 10
    assert 'suppressed' not in disclosure['suppressed_layers']


def test_late_visit_changes_scope_and_recomputes():
    base = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T2', '城北', 'other'),
        _answer('3', 'T2', '城北', 'direct'),
        _answer('4', 'T3', '末班', 'direct'),
    )
    before = run(base)['disclosure']
    assert set(before['suppressed_layers']) == {'枢纽', '末班'}
    # 晚到回访：枢纽补来第二份有效答卷，单答卷层变为多答卷层，公开范围重算
    updated = dict(base)
    updated['returns'] += '\n' + _answer('5', 'T1', '枢纽', 'other', visit=1)
    after = run(updated)['disclosure']
    assert after['suppressed_layers'] == ['末班']
    assert set(after['public_layers']) == {'枢纽', '城北'}
    # 全市照原数
    assert after['city']['integers'] == run(updated)['allocation']['totals']


def test_adjudicate_is_deterministic_across_runs():
    tables = _tables(
        _answer('1', 'T1', '枢纽', 'direct'),
        _answer('2', 'T2', '城北', 'direct'),
        _answer('3', 'T3', '末班', 'direct'),
    )
    first = run(tables)
    second = run(dict(tables))
    assert first['disclosure'] == second['disclosure']
    assert adjudicate(first['frame'], first['weights'], first['allocation'], first['balance']) == first['disclosure']
