from io import BytesIO
import pytest
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from extractor import analyze_pdf, analyze_pages, CVError


def pdf(pages):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    for items in pages:
        for x, y, text in items:
            c.drawString(x, y, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_bullets_and_section_boundaries():
    data = pdf([[(50,740,'TECHNICAL SKILLS'),(50,720,'Python, SQL, Docker'),
                 (50,700,'Python'),(50,660,'WORK EXPERIENCE'),
                 (50,640,'Built dashboards using Tableau.'),(50,600,'EDUCATION'),
                 (50,580,'Studied MATLAB in coursework.')]])
    r=analyze_pdf(data)
    assert set(r.skills)=={'Python','SQL','Docker','Tableau','MATLAB'}
    assert {e.section for e in r.evidence if e.skill=='Tableau'}=={'Work experience'}
    assert {e.section for e in r.evidence if e.skill=='MATLAB'}=={'Education'}
    assert len({e.skill for e in r.evidence if e.section=='Skills'})==3


def test_two_columns():
    r=analyze_pdf(pdf([[(40,740,'CORE COMPETENCIES'),(320,740,'PROJECTS'),
                       (40,720,'Python, PostgreSQL'),(320,720,'Built with React and Flask.'),
                       (40,700,'Docker'),(320,700,'Used Git for version control.')]]))
    assert {'Python','PostgreSQL','Docker','React','Flask','Git'} <= set(r.skills)
    assert all(e.section=='Projects' for e in r.evidence if e.skill in {'React','Flask','Git'})
    assert all(e.section=='Skills' for e in r.evidence if e.skill in {'Python','PostgreSQL','Docker'})


def test_table():
    r=analyze_pdf(pdf([[(40,740,'SKILLS'),(40,720,'Languages:'),(200,720,'Python, C++'),
                       (40,700,'Tools:'),(200,700,'Excel, Figma'),
                       (40,660,'EDUCATION'),(40,640,'University')]]))
    assert {'Python','C++','Excel','Figma'} <= set(r.skills)
    assert all(e.section=='Skills' for e in r.evidence)


def test_multiple_pages_and_aliases():
    r=analyze_pdf(pdf([[(40,740,'Skills: AWS, Amazon Web Services, sklearn')],
                       [(40,740,'PROJECTS'),(40,720,'Implemented a Python pipeline.')]]))
    assert len([e for e in r.evidence if e.skill=='AWS'])==1
    assert next(e for e in r.evidence if e.skill=='Python').page==2
    assert 'scikit-learn' in r.skills


def test_unknown_entries_and_no_prose():
    r=analyze_pages(['Technical Expertise\nQuantumSuite, WidgetCAD\nI developed software with customers\nAWARDS\nGold medal'])
    assert set(r.skills)=={'QuantumSuite','WidgetCAD'}
    assert all('review' in e.detection for e in r.evidence)


def test_negative_ambiguous_and_substrings():
    r=analyze_pages(['Summary\nI go to work and react to requests.\nNot familiar with Java.\nLearning Rust.\nJavaScript and MySQL\nSkills\nC++, C#, Go, R, Python'])
    assert {'Java','Rust','React','SQL','C','Git'}.isdisjoint(r.skills)
    assert {'JavaScript','MySQL','C++','C#','Go','R','Python'} <= set(r.skills)


def test_missing_heading():
    r=analyze_pages(['Built systems using Python and Docker.'])
    assert set(r.skills)=={'Python','Docker'}
    assert all(e.section=='Unsectioned' for e in r.evidence)
    assert r.warnings


def test_blank_pdf():
    r=analyze_pdf(pdf([[]]))
    assert not r.skills
    assert any('OCR' in w for w in r.warnings)


@pytest.mark.parametrize('data', [b'', b'not a pdf', b'%PDF-broken'])
def test_bad_pdf(data):
    with pytest.raises(CVError): analyze_pdf(data)


def test_encrypted():
    writer=PdfWriter()
    writer.append(PdfReader(BytesIO(pdf([[(40,740,'Skills: Python')]]))))
    writer.encrypt('test-password')
    buf=BytesIO(); writer.write(buf)
    with pytest.raises(CVError, match='encrypted'): analyze_pdf(buf.getvalue())
    assert analyze_pdf(buf.getvalue(), 'test-password').skills==['Python']


def test_limits():
    with pytest.raises(CVError, match='20 MB'): analyze_pdf(b'%PDF-'+b' '*(20*1024*1024))
    with pytest.raises(CVError, match='50-page'): analyze_pdf(pdf([[]]*51))


def test_unlabelled_skill_columns():
    r=analyze_pdf(pdf([[(40,740,'TECHNICAL SKILLS'),
                      (40,720,'Python'),(300,720,'Docker'),
                      (40,700,'SQL'),(300,700,'Excel')]]))
    assert set(r.skills)=={'Python','Docker','SQL','Excel'}
    assert all(e.section=='Skills' for e in r.evidence)


def test_every_evidence_has_source():
    r=analyze_pdf(pdf([[(40,740,'Skills: Python, Docker'),(40,700,'PROJECTS'),
                      (40,680,'Built a Streamlit tool.')]]))
    for e in r.evidence:
        assert e.snippet in ' '.join(r.pages[e.page-1].split())
        assert e.detection.startswith('Explicit')
