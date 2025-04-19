import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
import spacy

st.set_page_config(layout="wide")
st.title("🧬 Full-Text Bacteria Explorer")
st.markdown("Enter keywords to explore microbiome-related research papers with actual bacteria mentions from full-text or abstracts.")

@st.cache_resource
def load_model():
    import en_core_web_sm
    return en_core_web_sm.load()

nlp = load_model()

col1, col2 = st.columns(2)
with col1:
    keyword_1 = st.text_input("Keyword 1", value="pregnancy")
with col2:
    keyword_2 = st.text_input("Keyword 2", value="stress")

paper_limit = st.selectbox(
    "📄 How many papers would you like to search?",
    options=[30, 60, 100],
    index=0
)

if st.button("Search"):
    with st.spinner("⏳ Fetching papers and extracting bacteria..."):
        query = f'({keyword_1}[Title/Abstract]) AND ({keyword_2}[Title/Abstract]) AND (microbiome[Title/Abstract] OR gut[Title/Abstract] OR "gut microbiota"[Title/Abstract] OR flora[Title/Abstract] OR bacteria[Title/Abstract] OR "gut-brain axis"[Title/Abstract] OR HPA[Title/Abstract] OR "hypothalamic pituitary adrenal"[Title/Abstract])'

        today = datetime.today()
        start_date = (today - timedelta(days=3 * 365)).strftime("%Y/%m/%d")

        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"{query} AND ({start_date}[PDAT] : {today.strftime('%Y/%m/%d')}[PDAT])",
            "retmode": "json",
            "retmax": paper_limit,
            "sort": "pub+date"
        }

        response = requests.get(search_url, params=params).json()
        paper_ids = response.get("esearchresult", {}).get("idlist", [])
        st.success(f"🔍 Found {len(paper_ids)} papers")

        def get_pmc_id(pmid):
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&id={pmid}&retmode=json&linkname=pubmed_pmc"
            r = requests.get(url)
            links = r.json().get('linksets', [])
            if links and 'linksetdbs' in links[0]:
                for db in links[0]['linksetdbs']:
                    for link in db.get('links', []):
                        if link.startswith('PMC'):
                            return link.replace("PMC", "")
            return None

        def extract_text_from_pmc(pmcid):
            url = f"https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:{pmcid}&metadataPrefix=pmc"
            xml = requests.get(url).content
            soup = BeautifulSoup(xml, "xml")
            body = soup.find("body")
            if body:
                return body.get_text(separator=" ")
            return None

        def extract_bacteria_sentences(text):
            doc = nlp(text)
            sentences = list(doc.sents)
            results = defaultdict(list)
            mentioned = defaultdict(int)

            known_bacteria = set([
                "lactobacillus", "bifidobacterium", "faecalibacterium", "akkermansia", "clostridium", "prevotella",
                "bacteroides", "eubacterium", "coprococcus", "roseburia", "ruminococcus", "enterococcus", "escherichia",
                "streptococcus", "veillonella", "actinomyces", "peptostreptococcus", "alistipes", "parabacteroides",
                "blautia", "desulfovibrio", "butyricicoccus", "dialister", "oscillospira", "sutterella",
                "tannerella", "holdemania", "phocaeicola", "granulicatella", "megasphaera", "collinsella",
                "saricina", "clostridioides", "anaerostipes", "fusobacterium", "campylobacter", "peptococcus",
                "leptotrichia", "atopobium", "mobiluncus", "treponema", "methanobrevibacter",
                "ureaplasma", "mycoplasma", "eggerthella", "finegoldia", "peptoniphilus", "acinetobacter",
                "klebsiella", "pseudomonas", "weissella", "lactococcus", "cutibacterium",
                "corynebacterium", "neisseria", "gardnerella"
            ])

            text_lower = text.lower()
            for bac in known_bacteria:
                mentioned[bac] = text_lower.count(bac)

            for sent in sentences:
                sent_lower = sent.text.lower()
                for bac in known_bacteria:
                    if bac in sent_lower:
                        results[bac].append(sent.text.strip())

            return results, mentioned

        skipped_ids = []  # To track skipped papers

        for pid in paper_ids:
            try:
                summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pid}&retmode=json"
                summary = requests.get(summary_url).json()

                if "result" not in summary or pid not in summary["result"]:
                    skipped_ids.append(pid)
                    continue

                title = summary["result"][pid].get("title", "No title available")
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"

                pmcid = get_pmc_id(pid)
                if pmcid:
                    text = extract_text_from_pmc(pmcid)
                else:
                    fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pid}&retmode=xml"
                    fetch_response = requests.get(fetch_url)
                    soup = BeautifulSoup(fetch_response.content, "xml")
                    abstract = soup.find("AbstractText")
                    text = abstract.text if abstract else ""

                if text:
                    bac_sentences, bac_mentions = extract_bacteria_sentences(text)
                    if bac_sentences or any(v > 0 for v in bac_mentions.values()):
                        with st.expander(f"📄 {title}"):
                            st.markdown(f"[🔗 View on PubMed]({link})")
                            for bac, count in bac_mentions.items():
                                if count > 0:
                                    st.markdown(f"**🦠 {bac.capitalize()}** — mentioned {count} time(s)")
                                    if bac in bac_sentences:
                                        for s in bac_sentences[bac]:
                                            st.markdown(f"• _{s}_")
                                    else:
                                        st.markdown("_No exact sentence match found_")
                                    st.markdown("---")
            except Exception as e:
                st.warning(f"❌ Skipped paper {pid}: {e}")

        if skipped_ids:
            with st.expander("⚠️ Skipped Papers (missing summary metadata)"):
                for sid in skipped_ids:
                    st.markdown(f"❌ [PubMed ID {sid}](https://pubmed.ncbi.nlm.nih.gov/{sid}/)")

    st.success("✅ Extraction complete!")
