"""Conservative, evidence-first CV extraction. No remote services or model downloads."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from io import BytesIO
import re
import unicodedata
from pypdf import PdfReader

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 50

# Canonical name, category, explicit surface forms. Extend this small vocabulary
# without changing parsing; unknown list entries are retained only in skills sections.
CATALOG = {
 'Programming languages': {
  'Python': ['python'], 'Java': ['java'], 'JavaScript': ['javascript'],
  'TypeScript': ['typescript'], 'C++': ['c++'], 'C#': ['c#'], 'C': ['c'],
  'R': ['r'], 'SQL': ['sql'], 'Go': ['golang', 'go'], 'Rust': ['rust'],
  'Ruby': ['ruby'], 'PHP': ['php'], 'Swift': ['swift'], 'Kotlin': ['kotlin'],
  'MATLAB': ['matlab'], 'Bash': ['bash'], 'Scala': ['scala'], 'Dart': ['dart'],
 },
 'Frameworks & libraries': {
  'Streamlit': ['streamlit'], 'pypdf': ['pypdf'], 'pandas': ['pandas'],
  'NumPy': ['numpy'], 'scikit-learn': ['scikit-learn', 'sklearn'],
  'TensorFlow': ['tensorflow'], 'PyTorch': ['pytorch'], 'Django': ['django'],
  'Flask': ['flask'], 'FastAPI': ['fastapi'], 'React': ['react', 'react.js', 'reactjs'],
  'Angular': ['angular'], 'Vue': ['vue', 'vue.js'], 'Node.js': ['node.js', 'nodejs'],
  '.NET': ['.net', 'dotnet'], 'Spring Boot': ['spring boot'], 'Flutter': ['flutter'],
  'Spark': ['apache spark', 'pyspark', 'spark'], 'Hadoop': ['hadoop'],
 },
 'Cloud & DevOps': {
  'AWS': ['aws', 'amazon web services'], 'Azure': ['azure', 'microsoft azure'],
  'Google Cloud': ['gcp', 'google cloud'], 'Docker': ['docker'],
  'Kubernetes': ['kubernetes', 'k8s'], 'Terraform': ['terraform'],
  'Jenkins': ['jenkins'], 'GitHub Actions': ['github actions'], 'CI/CD': ['ci/cd'],
  'Ansible': ['ansible'], 'Linux': ['linux'], 'Git': ['git'],
 },
 'Databases': {
  'PostgreSQL': ['postgresql', 'postgres'], 'MySQL': ['mysql'],
  'SQLite': ['sqlite'], 'MongoDB': ['mongodb'], 'Redis': ['redis'],
  'Oracle Database': ['oracle database', 'oracle sql'], 'SQL Server': ['sql server'],
  'Snowflake': ['snowflake'], 'Elasticsearch': ['elasticsearch'],
 },
 'Software & tools': {
  'Excel': ['excel', 'microsoft excel', 'ms excel'], 'Power BI': ['power bi'],
  'Tableau': ['tableau'], 'Figma': ['figma'], 'AutoCAD': ['autocad'],
  'SolidWorks': ['solidworks'], 'Photoshop': ['photoshop'], 'Jira': ['jira'],
  'Salesforce': ['salesforce'], 'SAP': ['sap'], 'SPSS': ['spss'],
  'Microsoft Office': ['microsoft office', 'ms office'], 'Jupyter': ['jupyter'],
  'VS Code': ['vs code', 'visual studio code'], 'GitHub': ['github'],
 },
 'Methods & other skills': {
  'Machine learning': ['machine learning'], 'Deep learning': ['deep learning'],
  'Natural language processing': ['natural language processing', 'nlp'],
  'Data analysis': ['data analysis'], 'Data visualization': ['data visualization'],
  'Project management': ['project management'], 'Agile': ['agile'], 'Scrum': ['scrum'],
  'Communication': ['communication'], 'Leadership': ['leadership'],
  'Problem solving': ['problem solving', 'problem-solving'],
  'HTML': ['html', 'html5'], 'CSS': ['css', 'css3'], 'REST APIs': ['rest api', 'rest apis', 'restful apis'],
 }
}
SKILL_HEADINGS = {'skills', 'technical skills', 'core competencies', 'competencies',
 'key skills', 'professional skills', 'technical expertise', 'areas of expertise',
 'expertise', 'technical competencies', 'skills and abilities', 'skills & abilities',
 'skills and competencies', 'skills & competencies', 'tools and technologies',
 'technologies', 'skills summary', 'technical proficiencies', 'computer skills',
 'software skills', 'additional skills', 'relevant skills', 'core skills'}
SECTION_HEADINGS = {
 'Work experience': {'experience', 'work experience', 'professional experience', 'employment', 'employment history', 'career history', 'work history', 'internships'},
 'Projects': {'projects', 'personal projects', 'academic projects', 'selected projects', 'research projects'},
 'Education': {'education', 'academic background', 'qualifications', 'academic qualifications'},
 'Certifications': {'certifications', 'certificates', 'licenses', 'licenses and certifications'},
 'Summary': {'summary', 'profile', 'professional summary', 'objective', 'career objective', 'about me'},
 'Languages': {'languages', 'spoken languages'},
 'Other': {'interests', 'hobbies', 'awards', 'achievements', 'publications', 'references', 'volunteering', 'volunteer experience', 'activities', 'contact', 'contact information'},
}
SUBLABELS = {'languages', 'programming languages', 'programming', 'frameworks', 'libraries',
 'tools', 'software', 'databases', 'cloud', 'devops', 'technical', 'soft skills',
 'platforms', 'technologies', 'methodologies', 'design', 'data', 'other', 'skills'}

@dataclass(frozen=True)
class Evidence:
    skill: str
    category: str
    section: str
    page: int
    snippet: str
    detection: str  # Always explicit: no inferred capabilities are fabricated.

@dataclass
class Analysis:
    evidence: list[Evidence]
    pages: list[str]
    warnings: list[str]

    @property
    def skills(self):
        return sorted({e.skill for e in self.evidence}, key=str.casefold)

    def records(self):
        return [asdict(e) for e in self.evidence]

class CVError(ValueError):
    pass

def normalize(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip()

def heading(text):
    """Recognize whole heading labels, never substrings in prose."""
    clean = re.sub(r'^\s*[•●▪◦\-*\d.)]+\s*', '', text).strip()
    left, sep, tail = clean.partition(':')
    key = normalize(left).casefold().strip(' :–—-')
    if key in SKILL_HEADINGS:
        return 'Skills', tail.strip() if sep else ''
    for section, labels in SECTION_HEADINGS.items():
        if key in labels:
            return section, tail.strip() if sep else ''
    return None

def unknown_heading(line):
    s = line.strip().strip(':')
    return (3 <= len(s) <= 55 and len(s.split()) <= 6 and
            s.isupper() and not re.search(r'[,;|/•]', s) and
            not any(find_known(s, True)))

# Longest aliases first, so "Microsoft Excel" is a single supported mention.
PATTERNS = []
for category, entries in CATALOG.items():
    for canonical, aliases in entries.items():
        for alias in aliases:
            PATTERNS.append((canonical, category, re.compile(
                r'(?<![\w+#])' + re.escape(alias) + r'(?![\w+#])', re.I)))


def find_known(line, in_skills=False):
    hits = []
    for name, category, pattern in PATTERNS:
        for m in pattern.finditer(line):
            # Single-letter names and ordinary words need unambiguous casing/context.
            if name in {'C', 'R'} and m.group() != name:
                continue
            if name == 'Go' and m.group().lower() == 'go':
                if not in_skills or m.group() != 'Go':
                    continue
            # Avoid treating "React to customer requests" as a framework.
            if name == 'React' and re.search(r'^\s+to\b', line[m.end():], re.I):
                continue
            hits.append((m.start(), m.end(), name, category))
    selected = []
    for hit in sorted(hits, key=lambda h: (-(h[1]-h[0]), h[0])):
        if not any(hit[0] < h[1] and h[0] < hit[1] for h in selected):
            selected.append(hit)
    return sorted(selected)


def list_candidates(line):
    """Use section/list structure to retain explicit terms outside the vocabulary.

    Never promote prose sentences or headings to skills. Unknown terms are visibly
    marked for review rather than silently categorized as established technology.
    """
    line = re.sub(r'^\s*[•●▪◦*\-–]+\s*', '', line).strip()
    if ':' in line:
        label, line = line.split(':', 1)
        if len(label.split()) > 4:
            return []
    candidates = re.split(r'\s*[,;|•●▪]\s*|\s{2,}|\s+/\s+', line)
    result = []
    for part in candidates:
        part = re.sub(r'\s*\((?:advanced|intermediate|beginner|expert|proficient)\)\s*$', '', part, flags=re.I)
        part = re.sub(r'\s+[–—]\s+(?:advanced|intermediate|beginner|expert)$', '', part, flags=re.I).strip(' .')
        if not part or normalize(part).casefold() in SUBLABELS:
            continue
        words = part.split()
        if len(words) > 4 or len(part) > 48 or not re.search(r'[A-Za-z]', part):
            continue
        if re.search(r'\b(?:i|my|we|the|and|with|using|used|developed|built|worked|years?|experience|proficient|knowledge|responsible|familiar|including|ability|skills|not|no|without|learning)\b', part, re.I):
            continue
        if re.search(r'https?://|@|[.!?]$|\b\d{4}\b', part):
            continue
        # Known entries get their canonical spelling; a prose phrase containing a
        # known entry is not also emitted as a new unknown capability.
        if find_known(part, True):
            continue
        result.append(part)
    return result


def _negated(line, start):
    # Conservative local cue filter; future/aspirational mentions aren't evidence
    # of an existing skill. Keep the raw text available for human verification.
    prefix = line[max(0, start-65):start]
    return bool(re.search(r'\b(?:no|not|without|never|lack(?:ing)?|learning|learn|interested in|plan to learn|want to learn)\b[^,;|.]{0,45}$', prefix, re.I))


def analyze_pages(pages: list[str]) -> Analysis:
    evidence = []
    warnings = []
    seen = set()
    section = 'Unsectioned'
    skills_found = False
    for page_no, text in enumerate(pages, 1):
        if not text.strip():
            warnings.append(f'Page {page_no} has no extractable text. Scanned pages need OCR, which this app does not perform.')
    column_sections = {0: 'Unsectioned'}
    for page_no, text in enumerate(pages, 1):
        rows = []
        anchors = [0]
        for raw in text.splitlines():
            segments = list(re.finditer(r'\S.*?(?=\s{3,}\S|$)', raw))
            rows.append(segments)
            for seg in segments[1:]:
                if not any(abs(seg.start()-a) <= 8 for a in anchors):
                    anchors.append(seg.start())
        anchors.sort()
        if len(anchors) > 4:
            warnings.append(f'Page {page_no} has complex alignment; verify sections against the raw PDF text.')
        for segments in rows:
            table_section = None
            if segments:
                first = segments[0]
                first_column = min(anchors, key=lambda a: abs(a-first.start()))
                first_text = first.group().strip()
                if (column_sections.get(first_column) == 'Skills' and
                        first_text.endswith(':') and
                        first_text[:-1].casefold() in SUBLABELS):
                    table_section = 'Skills'
            for seg in segments:
                line = seg.group().strip()
                column = min(anchors, key=lambda a: abs(a-seg.start()))
                if column not in column_sections:
                    left = [a for a in column_sections if a < column]
                    inherited = column_sections[max(left)] if left else 'Unsectioned'
                    column_sections[column] = inherited if inherited == 'Skills' else 'Unsectioned'
                section = table_section or column_sections[column]
                if table_section and line.endswith(':') and line[:-1].casefold() in SUBLABELS:
                    continue
                h = heading(line)
                if h:
                    section, line = h
                    column_sections[column] = section
                    skills_found |= section == 'Skills'
                    if not line:
                        continue
                elif section == 'Skills' and unknown_heading(line):
                    # Unrecognized uppercase headings close a skills block.
                    column_sections[column] = 'Other'
                    continue
                for start, end, name, category in find_known(line, section == 'Skills'):
                    if _negated(line, start):
                        continue
                    # Single letters outside a skills block need an explicit cue.
                    if name in {'C', 'R'} and section != 'Skills' and not re.search(r'\b(?:programming|language|using|in)\s+' + name + r'\b', line):
                        continue
                    entry = Evidence(name, category, section, page_no, normalize(line), 'Explicit mention')
                    key = (name.casefold(), section, page_no, entry.snippet)
                    if key not in seen:
                        seen.add(key)
                        evidence.append(entry)
                if section == 'Skills':
                    for name in list_candidates(line):
                        key = (name.casefold(), section, page_no, normalize(line))
                        if key not in seen:
                            seen.add(key)
                            evidence.append(Evidence(name, 'Other listed skills — review', section, page_no, normalize(line), 'Explicit list entry — review'))
    if not skills_found:
        warnings.append('No recognized Skills heading was found. Results contain explicit mentions from other sections only.')
    return Analysis(sorted(evidence, key=lambda e: (e.skill.casefold(), e.page, e.section)), pages, list(dict.fromkeys(warnings)))


def analyze_pdf(data: bytes, password: str = '') -> Analysis:
    if not data:
        raise CVError('Upload a non-empty PDF file.')
    if len(data) > MAX_BYTES:
        raise CVError('The PDF exceeds the 20 MB limit.')
    if not data.lstrip().startswith(b'%PDF-'):
        raise CVError('This file is not a valid PDF. Please upload a PDF document.')
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(password):
            raise CVError('This PDF is encrypted. Enter the correct PDF password and try again.')
        if len(reader.pages) > MAX_PAGES:
            raise CVError('The PDF exceeds the 50-page limit. Upload a shorter CV.')
        pages = [p.extract_text(extraction_mode='layout') or '' for p in reader.pages]
    except CVError:
        raise
    except Exception as exc:
        raise CVError('The PDF could not be read. It may be damaged or use unsupported encryption. Try exporting it as a new PDF.') from exc
    result = analyze_pages(pages)
    if not any(t.strip() for t in pages):
        result.warnings.append('No readable text was found. Export a text-based PDF or run OCR before uploading.')
    return result
