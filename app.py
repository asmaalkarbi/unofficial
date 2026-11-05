"""Launch with: streamlit run app.py"""
import csv
import hashlib
import io
import streamlit as st
from extractor import analyze_pdf, CVError

st.set_page_config(page_title='CV Skill Explorer', page_icon='📄', layout='wide')
st.title('📄 CV Skill Explorer')
st.write('Find the skills your CV explicitly mentions, with evidence you can verify.')
st.caption('Python • Streamlit • pypdf | No AI API, external uploads, or inferred skills')
with st.sidebar:
    st.header('How it works')
    st.write('1. Upload a text-based PDF.\n2. Select Analyze CV.\n3. Review skills, sections, and supporting text.')
    st.info('Scanned PDFs need OCR first. Complex layouts and unknown headings can affect section detection. Always review the source snippets.')
    st.caption('Your PDF is processed in this app session. It is not written to disk by the application or sent to an external service. Your hosting provider controls infrastructure logs and session access.')
    if st.button('Clear analysis'):
        st.session_state.pop('analysis', None)
        st.session_state.pop('analysis_key', None)

upload = st.file_uploader('Upload your CV', type=['pdf'], help='Text-based PDF, up to 20 MB and 50 pages.')
password = st.text_input('PDF password (only if encrypted)', type='password')
data = upload.getvalue() if upload else None
key = hashlib.sha256(data).hexdigest() if data else None
if st.session_state.get('analysis_key') != key:
    st.session_state.pop('analysis', None)
if st.button('Analyze CV', type='primary', disabled=upload is None):
    st.session_state.pop('analysis', None)
    try:
        with st.spinner('Reading PDF and locating skill evidence…'):
            result = analyze_pdf(data, password)
        st.session_state.analysis = result
        st.session_state.analysis_key = key
    except CVError as exc:
        st.error(str(exc))
    except Exception:
        st.error('Analysis could not finish. Try a smaller PDF or export a fresh text-based copy.')

result = st.session_state.get('analysis')
if result is not None:
    a, b, c = st.columns(3)
    a.metric('Unique detected skills', len(result.skills))
    b.metric('Listed in Skills section', len({e.skill for e in result.evidence if e.section == 'Skills'}))
    c.metric('Pages analyzed', len(result.pages))
    for warning in result.warnings:
        st.warning(warning)
    st.caption('Every result is explicitly supported by extracted text. No inferred skills are generated. Unknown short list entries are labeled for review; mentions do not prove proficiency.')
    if not result.evidence:
        st.info('No supported skills detected. Check the extracted text below. The vocabulary is deliberately conservative.')
    else:
        sections = sorted({e.section for e in result.evidence}, key=lambda s: (s != 'Skills', s))
        chosen = st.multiselect('CV sections', sections, default=sections)
        categories = sorted({e.category for e in result.evidence})
        selected = st.multiselect('Skill categories', categories, default=categories)
        view = [e for e in result.evidence if e.section in chosen and e.category in selected]
        skill_tab, evidence_tab = st.tabs(['Grouped skills', 'All source evidence'])
        with skill_tab:
            for section in chosen:
                entries = [e for e in view if e.section == section]
                if not entries:
                    continue
                st.subheader(section)
                for category in selected:
                    group = [e for e in entries if e.category == category]
                    if not group:
                        continue
                    st.write(f'**{category}**')
                    for name in sorted({e.skill for e in group}, key=str.casefold):
                        matches = [e for e in group if e.skill == name]
                        pages = ', '.join(str(p) for p in sorted({e.page for e in matches}))
                        with st.expander(f'{name} · page {pages}'):
                            for e in matches:
                                st.caption(f'Page {e.page} · {e.section} · {e.detection}')
                                st.text(e.snippet)
        with evidence_tab:
            st.dataframe([e.__dict__ for e in view], use_container_width=True, hide_index=True)
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=['skill','category','section','page','snippet','detection'])
        writer.writeheader()
        for row in result.records():
            # Protect spreadsheet consumers from formula injection in PDF content.
            writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v) for k,v in row.items()})
        st.download_button('Download skill evidence (CSV)', out.getvalue(), 'cv-skills.csv', 'text/csv')
    with st.expander('Original extracted PDF text', expanded=not bool(result.evidence)):
        st.caption('Layout text returned by pypdf. This is not a visual rendering of the PDF.')
        for page_no, text in enumerate(result.pages, 1):
            st.write(f'**Page {page_no}**')
            st.text(text or '[No extractable text]')
