from pathlib import Path
from streamlit.testing.v1 import AppTest
from extractor import analyze_pages

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def test_initial_interface():
    at=AppTest.from_file(APP).run()
    assert not at.exception
    assert at.title[0].value=='📄 CV Skill Explorer'
    assert next(b for b in at.button if b.label=='Analyze CV').disabled


def test_results_and_filters():
    at=AppTest.from_file(APP)
    at.session_state['analysis']=analyze_pages(['Skills\nPython, Docker\nProjects\nBuilt with Flask.'])
    at.session_state['analysis_key']=None
    at.run()
    assert not at.exception
    assert at.metric[0].value=='3'
    assert any(e.label=='Python · page 1' for e in at.expander)
    at.multiselect[0].set_value(['Projects']).run()
    assert not at.exception
    assert any(e.label=='Flask · page 1' for e in at.expander)
    assert not any(e.label=='Python · page 1' for e in at.expander)
    next(b for b in at.button if b.label=='Clear analysis').click().run()
    assert not at.metric


def test_empty_result():
    at=AppTest.from_file(APP)
    at.session_state['analysis']=analyze_pages([''])
    at.session_state['analysis_key']=None
    at.run()
    assert not at.exception
    assert at.metric[0].value=='0'
    assert at.warning
