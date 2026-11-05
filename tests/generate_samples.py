"""Generate synthetic PDFs for manual upload testing; no personal information."""
from pathlib import Path
from reportlab.pdfgen import canvas


def main():
    folder = Path(__file__).resolve().parents[1] / 'samples'
    folder.mkdir(exist_ok=True)
    layouts = {
        'standard.pdf': [[(40,750,'EXAMPLE CV'),(40,710,'TECHNICAL SKILLS'),
            (40,690,'Python, SQL, Docker'),(40,670,'Frameworks: Streamlit, pandas'),
            (40,630,'WORK EXPERIENCE'),(40,610,'Built reports using Power BI.'),
            (40,570,'EDUCATION'),(40,550,'Used MATLAB in coursework.')]],
        'two-columns.pdf': [[(40,740,'CORE COMPETENCIES'),(320,740,'PROJECTS'),
            (40,720,'Python, PostgreSQL'),(320,720,'Built with React and Flask.'),
            (40,700,'Docker, Git'),(320,700,'Deployed to AWS.')]],
        'table.pdf': [[(40,740,'SKILLS'),(40,720,'Languages:'),(200,720,'Python, C++'),
            (40,700,'Tools:'),(200,700,'Excel, Figma'),(40,660,'EDUCATION')]],
        'multiple-pages.pdf': [[(40,740,'Technical Expertise: AWS, sklearn')],
            [(40,740,'PROJECTS'),(40,720,'Implemented a Python pipeline.')]],
        'scanned-placeholder.pdf': [[]],
    }
    for filename, pages in layouts.items():
        c=canvas.Canvas(str(folder / filename), pagesize=(612,792))
        for items in pages:
            for x,y,text in items: c.drawString(x,y,text)
            c.showPage()
        c.save()
    print(f'Generated {len(layouts)} sample PDFs in {folder}')


if __name__=='__main__': main()
