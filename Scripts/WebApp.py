import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
import atexit

# Configurazione della pagina
st.set_page_config(
    page_title="ComicGraph",
    page_icon="💭",
    layout="wide"
)

# Parametri di connessione a Neo4j
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

@st.cache_resource
def get_driver():
    drv = GraphDatabase.driver(URI, auth=AUTH)
    atexit.register(drv.close)
    return drv

try:
    driver = get_driver()
    with driver.session() as s:
        s.run("RETURN 1")
    db_connected = True
except Exception as e:
    db_connected = False
    db_error = str(e)

# Header principale
st.title("ComicGraph")
st.markdown("Piattaforma di esplorazione e gestione dei cataloghi fumettistici")

if not db_connected:
    st.error(f"Connessione al database non riuscita su {URI}. Verificare che il server Neo4j sia attivo.\n\nErrore: {db_error}")
    st.stop()

# Sidebar: Riepilogo del database
with st.sidebar:
    st.header("Informazioni Database")
    with driver.session() as session:
        n_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        n_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        n_issues = session.run("MATCH (i:Issue) RETURN count(i) AS c").single()["c"]
        n_chars = session.run("MATCH (c:Character) RETURN count(c) AS c").single()["c"]
        n_series = session.run("MATCH (s:Series) RETURN count(s) AS c").single()["c"]
        n_creators = session.run("MATCH (cr:Creator) RETURN count(cr) AS c").single()["c"]
        n_pubs = session.run("MATCH (p:Publisher) RETURN count(p) AS c").single()["c"]
    
    col_stat1, col_stat2 = st.columns(2)
    col_stat1.metric("Nodi Totali", f"{n_nodes:,}")
    col_stat2.metric("Relazioni", f"{n_rels:,}")
    
    col_stat3, col_stat4 = st.columns(2)
    col_stat3.metric("Albi (Issues)", f"{n_issues:,}")
    col_stat4.metric("Personaggi", f"{n_chars:,}")

    col_stat5, col_stat6 = st.columns(2)
    col_stat5.metric("Serie", f"{n_series:,}")
    col_stat6.metric("Autori", f"{n_creators:,}")
    
    st.metric("Editori", f"{n_pubs}")
    
    st.markdown("---")
    st.subheader("Entita Catalogate")
    st.markdown("""
    * Personaggi (Character)
    * Albi e Fumetti (Issue)
    * Serie e Testate (Series)
    * Autori e Creativi (Creator)
    * Editori (Publisher)
    """)

# Schede di navigazione dell'applicazione
tab_read, tab_create, tab_update, tab_delete, tab_join = st.tabs([
    "Esplora Catalogo",
    "Nuovo Record",
    "Modifica Dati",
    "Elimina Record",
    "Autori e Collaborazioni"
])

ENTITIES_LIST = [
    "Personaggio (Character)", 
    "Albo (Issue)", 
    "Serie (Series)", 
    "Autore (Creator)", 
    "Editore (Publisher)"
]

#esplora catalogo
with tab_read:
    st.subheader("Ricerca nel Database")
    read_entity = st.radio("Seleziona l'entita da cercare:", ENTITIES_LIST, horizontal=True, key="rad_read")
    
    # personaggi
    if read_entity == "Personaggio (Character)":
        search_query = st.text_input("Nome del personaggio:", value="Batman")
        if st.button("Cerca Personaggio", key="btn_read_char"):
            with driver.session() as session:
                q_char = """
                    MATCH (c:Character)-[:PUBLISHED_BY]->(p:Publisher)
                    WHERE toLower(c.name) CONTAINS toLower($name)
                    RETURN c.id AS ID, 
                           c.name AS Nome, 
                           p.name AS Editore, 
                           c.alignment AS Allineamento, 
                           c.first_appearance_year AS AnnoDebutto,
                           c.appearances_count AS Presenze, 
                           c.status AS Stato
                    ORDER BY c.appearances_count DESC
                    LIMIT 15
                """
                res_char = list(session.run(q_char, name=search_query))
                if res_char:
                    st.success(f"Trovati {len(res_char)} personaggi corrispondenti:")
                    df_char = pd.DataFrame([dict(r) for r in res_char])
                    st.dataframe(df_char, use_container_width=True)
                    
                    first_name = res_char[0]["Nome"]
                    q_series = """
                        MATCH (c:Character {name: $name})-[r:STARS_IN]->(s:Series)
                        RETURN s.name AS Serie
                        ORDER BY Serie ASC
                    """
                    res_series = list(session.run(q_series, name=first_name))
                    st.markdown(f"**Serie con protagonista `{first_name}` ({len(res_series)} serie collegate):**")
                    if res_series:
                        preview_series = [f"`{r['Serie']}`" for r in res_series[:15]]
                        if len(res_series) > 15:
                            st.write(", ".join(preview_series))
                            with st.expander(f"... Espandi per visualizzare tutte le {len(res_series)} serie collegate"):
                                st.write(", ".join([f"`{r['Serie']}`" for r in res_series]))
                        else:
                            st.write(", ".join(preview_series))
                    else:
                        st.info("Nessuna serie registrata come protagonista principale per questo personaggio.")
                else:
                    st.warning("Nessun personaggio trovato.")

    #Albi (Issue)
    elif read_entity == "Albo (Issue)":
        search_issue = st.text_input("Titolo o numero dell'albo:", value="Action Comics #1")
        if st.button("Cerca Albo", key="btn_read_issue"):
            with driver.session() as session:
                q_issue = """
                    MATCH (i:Issue)-[:PART_OF_SERIES]->(s:Series)
                    MATCH (i)-[:PUBLISHED_BY]->(p:Publisher)
                    OPTIONAL MATCH (cr_w:Creator)-[:WROTE]->(i)
                    OPTIONAL MATCH (cr_p:Creator)-[:PENCILED]->(i)
                    WHERE toLower(i.title) CONTAINS toLower($title)
                    RETURN i.id AS ID, 
                           i.title AS TitoloAlbo, 
                           s.name AS Serie, 
                           p.code AS Editore, 
                           i.release_year AS Anno, 
                           collect(DISTINCT cr_w.name) AS Scrittori, 
                           collect(DISTINCT cr_p.name) AS Disegnatori
                    ORDER BY Anno ASC
                    LIMIT 20
                """
                res_issue = list(session.run(q_issue, title=search_issue))
                if res_issue:
                    st.success(f"Trovati {len(res_issue)} albi corrispondenti:")
                    data_issues = []
                    for r in res_issue:
                        w_str = ", ".join(r["Scrittori"]) if r["Scrittori"] else "N/D"
                        p_str = ", ".join(r["Disegnatori"]) if r["Disegnatori"] else "N/D"
                        data_issues.append({
                            "ID": r["ID"],
                            "Titolo": r["TitoloAlbo"],
                            "Serie": r["Serie"],
                            "Editore": r["Editore"],
                            "Anno": r["Anno"],
                            "Scrittori": w_str,
                            "Disegnatori": p_str
                        })
                    st.dataframe(pd.DataFrame(data_issues), use_container_width=True)
                else:
                    st.warning("Nessun albo trovato.")

    #Serie (Series)
    elif read_entity == "Serie (Series)":
        search_series = st.text_input("Titolo della serie:", value="The Punisher")
        if st.button("Cerca Serie", key="btn_read_series"):
            with driver.session() as session:
                q_ser = """
                    MATCH (s:Series)
                    WHERE toLower(s.name) CONTAINS toLower($title)
                    OPTIONAL MATCH (i:Issue)-[:PART_OF_SERIES]->(s)
                    OPTIONAL MATCH (c:Character)-[:STARS_IN]->(s)
                    RETURN s.name AS NomeSerie, 
                           count(DISTINCT i) AS NumeroAlbi, 
                           collect(DISTINCT c.name) AS Protagonisti
                    ORDER BY NumeroAlbi DESC
                    LIMIT 15
                """
                res_ser = list(session.run(q_ser, title=search_series))
                if res_ser:
                    st.success(f"Trovate {len(res_ser)} serie corrispondenti:")
                    data_ser = []
                    for r in res_ser:
                        prot_str = ", ".join(r["Protagonisti"]) if r["Protagonisti"] else "N/D"
                        data_ser.append({
                            "Serie": r["NomeSerie"],
                            "Albi Totali": r["NumeroAlbi"],
                            "Protagonisti": prot_str
                        })
                    st.dataframe(pd.DataFrame(data_ser), use_container_width=True)
                else:
                    st.warning("Nessuna serie trovata.")

    #Autori (Creator)
    elif read_entity == "Autore (Creator)":
        search_cr = st.text_input("Nome dell'autore:", value="Frank Miller")
        if st.button("Cerca Autore", key="btn_read_creator"):
            with driver.session() as session:
                q_cr = """
                    MATCH (cr:Creator)
                    WHERE toLower(cr.name) CONTAINS toLower($name)
                    OPTIONAL MATCH (cr)-[:WROTE]->(i_w:Issue)
                    OPTIONAL MATCH (cr)-[:PENCILED]->(i_p:Issue)
                    OPTIONAL MATCH (cr)-[:COVER_ARTIST_FOR]->(i_c:Issue)
                    RETURN cr.name AS Autore, 
                           count(DISTINCT i_w) AS AlbiScritti, 
                           count(DISTINCT i_p) AS AlbiDisegnati, 
                           count(DISTINCT i_c) AS Copertine
                    ORDER BY (AlbiScritti + AlbiDisegnati) DESC
                    LIMIT 15
                """
                res_cr = list(session.run(q_cr, name=search_cr))
                if res_cr:
                    st.success(f"Trovati {len(res_cr)} autori corrispondenti:")
                    st.dataframe(pd.DataFrame([dict(r) for r in res_cr]), use_container_width=True)
                    
                    target_author = res_cr[0]["Autore"]
                    q_works = """
                        MATCH (cr:Creator {name: $name})-[r]->(i:Issue)
                        OPTIONAL MATCH (i)-[:PART_OF_SERIES]->(ser:Series)
                        RETURN i.title AS Albo, 
                               ser.name AS Serie, 
                               collect(DISTINCT type(r)) AS Ruoli, 
                               i.release_year AS Anno
                        ORDER BY Anno DESC, Albo ASC
                    """
                    res_works = list(session.run(q_works, name=target_author))
                    st.markdown(f"**Lavori e albi collegati a `{target_author}` ({len(res_works)} opere trovate):**")
                    if res_works:
                        role_map = {'WROTE': 'Scrittore', 'PENCILED': 'Disegnatore', 'COVER_ARTIST_FOR': 'Copertinista'}
                        data_works = []
                        for r in res_works:
                            ruoli_str = ", ".join([role_map.get(x, x) for x in r["Ruoli"]])
                            data_works.append({
                                "Albo": r["Albo"],
                                "Serie": r["Serie"] if r["Serie"] else "N/D",
                                "Ruolo Svolto": ruoli_str,
                                "Anno": r["Anno"] if r["Anno"] else "N/D"
                            })
                        df_works = pd.DataFrame(data_works)
                        if len(df_works) > 15:
                            st.dataframe(df_works.head(15), use_container_width=True)
                            with st.expander(f"... Espandi per visualizzare tutti i {len(df_works)} albi collegati"):
                                st.dataframe(df_works, use_container_width=True)
                        else:
                            st.dataframe(df_works, use_container_width=True)
                    else:
                        st.info("Nessun albo collegato registrato per questo autore.")
                else:
                    st.warning("Nessun autore trovato.")

    #Editori (Publisher)
    elif read_entity == "Editore (Publisher)":
        if st.button("Elenca Editori", key="btn_read_pub"):
            with driver.session() as session:
                q_pub = """
                    MATCH (p:Publisher)
                    OPTIONAL MATCH (c:Character)-[:PUBLISHED_BY]->(p)
                    WITH p, count(DISTINCT c) AS TotalePersonaggi
                    OPTIONAL MATCH (i:Issue)-[:PUBLISHED_BY]->(p)
                    RETURN p.code AS Codice, 
                           p.name AS NomeEditore, 
                           TotalePersonaggi, 
                           count(DISTINCT i) AS TotaleAlbi
                    ORDER BY TotaleAlbi DESC
                """
                res_pub = list(session.run(q_pub))
                if res_pub:
                    st.success(f"Trovati {len(res_pub)} editori registrati:")
                    st.dataframe(pd.DataFrame([dict(r) for r in res_pub]), use_container_width=True)
                else:
                    st.warning("Nessun editore trovato.")

#Create
with tab_create:
    st.subheader("Registrazione Nuovo Record")
    st.caption("Inserimento nuove entità")
    create_type = st.radio("Seleziona l'entita da creare:", ENTITIES_LIST, horizontal=True, key="rad_create")
    
    #Personaggio
    if create_type == "Personaggio (Character)":
        with st.form("form_create_char"):
            col_c1, col_c2 = st.columns(2)
            new_char_id = col_c1.text_input("Identificativo univoco (ID):", value="custom_hero_01")
            new_char_name = col_c2.text_input("Nome completo (es. 'Moon Knight (Marc Spector)'):", value="Captain Future")
            
            col_c3, col_c4, col_c5 = st.columns(3)
            new_char_pub = col_c3.selectbox("Editore:", ["DC", "Marvel"])
            new_char_align = col_c4.selectbox("Allineamento:", ["Good", "Neutral", "Bad"])
            new_char_year = col_c5.number_input("Anno di debutto:", min_value=1930, max_value=2030, value=2026)
            
            new_char_custom_series = st.text_input("Serie di collegamento:", value="")
            
            submit_c_char = st.form_submit_button("Salva Personaggio")
            
        if submit_c_char:
            if not new_char_id.strip() or not new_char_name.strip():
                st.error("ID e Nome sono campi obbligatori.")
            else:
                alias = new_char_name.split("(")[0].strip()
                with driver.session() as session:
                    q_create_c = """
                        MERGE (c:Character {id: $id})
                        SET c.name = $name,
                            c.alignment = $alignment,
                            c.first_appearance_year = toInteger($year),
                            c.appearances_count = 1,
                            c.status = 'Attivo'
                        WITH c
                        MATCH (p:Publisher {code: $publisher})
                        MERGE (c)-[:PUBLISHED_BY]->(p)
                        WITH c, p
                        FOREACH (_ IN CASE WHEN $custom_series <> '' THEN [1] ELSE [] END |
                            MERGE (cs:Series {name: $custom_series})
                            MERGE (c)-[:STARS_IN]->(cs)
                        )
                        WITH c, p
                        OPTIONAL MATCH (s:Series)
                        WHERE size($alias) >= 4 AND toLower(s.name) CONTAINS toLower($alias)
                        FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (c)-[:STARS_IN]->(s)
                        )
                        WITH c, p
                        OPTIONAL MATCH (c)-[:STARS_IN]->(all_s:Series)
                        RETURN c.id AS id, 
                               c.name AS name, 
                               p.name AS publisher, 
                               count(DISTINCT all_s) AS total_series, 
                               collect(DISTINCT all_s.name)[0..5] AS sample_series
                    """
                    res = session.run(
                        q_create_c, 
                        id=new_char_id.strip(), 
                        name=new_char_name.strip(), 
                        alignment=new_char_align, 
                        year=new_char_year, 
                        publisher=new_char_pub,
                        custom_series=new_char_custom_series.strip(),
                        alias=alias
                    ).single()
                    
                    st.success(f"Personaggio '{res['name']}' (ID: {res['id']}) registrato con successo sotto {res['publisher']}.")
                    sample_txt = ", ".join(res['sample_series']) if res['sample_series'] else "Nessuna serie corrispondente per ora"
                    st.info(f"Regola relazionale retroattiva applicata: collegato a {res['total_series']} serie tramite la relazione STARS_IN. Esempi: {sample_txt}")

    #Albo (Issue)
    elif create_type == "Albo (Issue)":
        with st.form("form_create_issue"):
            col_i1, col_i2 = st.columns(2)
            new_iss_id = col_i1.text_input("Identificativo Albo (ID):", value="custom_issue_01")
            new_iss_title = col_i2.text_input("Titolo Albo:", value="The Amazing Spider-Man #1000")
            
            col_i3, col_i4 = st.columns(2)
            new_iss_series = col_i3.text_input("Serie di appartenenza:", value="The Amazing Spider-Man")
            new_iss_pub = col_i4.selectbox("Editore Albo:", ["Marvel", "DC"])
            
            new_iss_year = st.number_input("Anno di pubblicazione:", min_value=1930, max_value=2030, value=2026)
            
            st.markdown("**Crediti e Autori dell'Albo**")
            col_cr1, col_cr2, col_cr3 = st.columns(3)
            new_iss_writer = col_cr1.text_input("Scrittore (WROTE):", value="Stan Lee")
            new_iss_penciler = col_cr2.text_input("Disegnatore (PENCILED):", value="Steve Ditko")
            new_iss_cover = col_cr3.text_input("Copertinista (COVER_ARTIST_FOR):", value="")
            
            submit_c_iss = st.form_submit_button("Salva Albo")
            
        if submit_c_iss:
            if not new_iss_id.strip() or not new_iss_title.strip() or not new_iss_series.strip():
                st.error("ID, Titolo e Serie sono campi obbligatori.")
            else:
                with driver.session() as session:
                    q_create_i = """
                        MERGE (i:Issue {id: $id})
                        SET i.title = $title,
                            i.release_year = toInteger($year)
                        MERGE (s:Series {name: $series})
                        MERGE (i)-[:PART_OF_SERIES]->(s)
                        WITH i, s
                        MATCH (p:Publisher {code: $publisher})
                        MERGE (i)-[:PUBLISHED_BY]->(p)
                        WITH i, s
                        FOREACH (_ IN CASE WHEN $writer <> '' THEN [1] ELSE [] END |
                            MERGE (w:Creator {name: $writer})
                            MERGE (w)-[:WROTE]->(i)
                        )
                        FOREACH (_ IN CASE WHEN $penciler <> '' THEN [1] ELSE [] END |
                            MERGE (penc:Creator {name: $penciler})
                            MERGE (penc)-[:PENCILED]->(i)
                        )
                        FOREACH (_ IN CASE WHEN $cover <> '' THEN [1] ELSE [] END |
                            MERGE (cov:Creator {name: $cover})
                            MERGE (cov)-[:COVER_ARTIST_FOR]->(i)
                        )
                        WITH i, s
                        OPTIONAL MATCH (c:Character)
                        WHERE size(split(c.name, ' (')[0]) >= 4 
                          AND toLower(s.name) CONTAINS toLower(split(c.name, ' (')[0])
                        FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (c)-[:STARS_IN]->(s)
                        )
                        WITH i, s
                        OPTIONAL MATCH (hero:Character)-[:STARS_IN]->(s)
                        RETURN i.id AS id, 
                               i.title AS title, 
                               s.name AS series, 
                               collect(DISTINCT hero.name)[0..5] AS heroes
                    """
                    res = session.run(
                        q_create_i, 
                        id=new_iss_id.strip(), 
                        title=new_iss_title.strip(), 
                        series=new_iss_series.strip(), 
                        publisher=new_iss_pub, 
                        year=new_iss_year, 
                        writer=new_iss_writer.strip(),
                        penciler=new_iss_penciler.strip(),
                        cover=new_iss_cover.strip()
                    ).single()
                    
                    st.success(f"Albo '{res['title']}' (ID: {res['id']}) inserito con successo.")
                    prot_txt = ", ".join(res['heroes']) if res['heroes'] else "Nessun personaggio collegato per ora"
                    st.info(f"Relazioni create: PART_OF_SERIES con '{res['series']}', PUBLISHED_BY con {new_iss_pub}, ruoli autori registrati. Protagonisti della serie: {prot_txt}")

    #Serie (Series)
    elif create_type == "Serie (Series)":
        with st.form("form_create_series"):
            new_ser_name = st.text_input("Nome della nuova Serie (es. 'Daredevil: Born Again (2026)'):", value="Secret Invasion: Reborn (2026)")
            col_s1, col_s2 = st.columns(2)
            new_ser_pub = col_s1.selectbox("Editore di riferimento:", ["Marvel", "DC"])
            new_ser_char_hint = col_s2.text_input("Personaggio protagonista da associare subito (opzionale):", value="")
            
            submit_c_ser = st.form_submit_button("Salva Serie")
            
        if submit_c_ser:
            if not new_ser_name.strip():
                st.error("Il nome della serie e obbligatorio.")
            else:
                with driver.session() as session:
                    q_c_ser = """
                        MERGE (s:Series {name: $name})
                        WITH s
                        FOREACH (_ IN CASE WHEN $char_hint <> '' THEN [1] ELSE [] END |
                            MERGE (ch:Character {name: $char_hint})
                            MERGE (ch)-[:STARS_IN]->(s)
                        )
                        WITH s
                        OPTIONAL MATCH (c:Character)
                        WHERE size(split(c.name, ' (')[0]) >= 4 
                          AND toLower($name) CONTAINS toLower(split(c.name, ' (')[0])
                        FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (c)-[:STARS_IN]->(s)
                        )
                        WITH s
                        OPTIONAL MATCH (i:Issue)
                        WHERE toLower(i.title) CONTAINS toLower(split($name, ' (')[0])
                        FOREACH (_ IN CASE WHEN i IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (i)-[:PART_OF_SERIES]->(s)
                        )
                        WITH s
                        OPTIONAL MATCH (hero:Character)-[:STARS_IN]->(s)
                        OPTIONAL MATCH (iss:Issue)-[:PART_OF_SERIES]->(s)
                        RETURN s.name AS name, 
                               count(DISTINCT hero) AS total_heroes, 
                               collect(DISTINCT hero.name)[0..5] AS heroes,
                               count(DISTINCT iss) AS total_issues
                    """
                    res = session.run(
                        q_c_ser, 
                        name=new_ser_name.strip(),
                        char_hint=new_ser_char_hint.strip()
                    ).single()
                    
                    st.success(f"Serie '{res['name']}' creata con successo nel catalogo.")
                    heroes_txt = ", ".join(res['heroes']) if res['heroes'] else "Nessuno trovato in automatico"
                    st.info(f"Regola retroattiva applicata: collegati {res['total_heroes']} personaggi protagonisti ({heroes_txt}) e {res['total_issues']} albi esistenti alla serie.")

    #Autore (Creator)
    elif create_type == "Autore (Creator)":
        with st.form("form_create_creator"):
            new_cr_name = st.text_input("Nome e Cognome dell'autore / artista:", value="Chip Zdarsky")
            col_cr_a, col_cr_b = st.columns(2)
            new_cr_role = col_cr_a.selectbox("Ruolo da assegnare negli albi collegati:", ["Scrittore (WROTE)", "Disegnatore (PENCILED)", "Copertinista (COVER_ARTIST_FOR)"])
            new_cr_target_issue = col_cr_b.text_input("Titolo o ID albo a cui associarlo retroattivamente (opzionale):", value="")
            
            submit_c_cr = st.form_submit_button("Salva Autore")
            
        if submit_c_cr:
            if not new_cr_name.strip():
                st.error("Il nome dell'autore e obbligatorio.")
            else:
                rel_type = "WROTE"
                if "PENCILED" in new_cr_role:
                    rel_type = "PENCILED"
                elif "COVER_ARTIST_FOR" in new_cr_role:
                    rel_type = "COVER_ARTIST_FOR"
                
                with driver.session() as session:
                    q_c_cr = f"""
                        MERGE (cr:Creator {{name: $name}})
                        WITH cr
                        OPTIONAL MATCH (i:Issue)
                        WHERE $target <> '' AND (i.id = $target OR toLower(i.title) CONTAINS toLower($target))
                        FOREACH (_ IN CASE WHEN i IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (cr)-[:{rel_type}]->(i)
                        )
                        WITH cr
                        OPTIONAL MATCH (cr)-[r]->(iss:Issue)
                        RETURN cr.name AS name, 
                               count(iss) AS total_works, 
                               collect(iss.title)[0..5] AS sample_works
                    """
                    res = session.run(q_c_cr, name=new_cr_name.strip(), target=new_cr_target_issue.strip()).single()
                    st.success(f"Autore '{res['name']}' aggiunto all'anagrafica degli artisti.")
                    if res['total_works'] > 0:
                        works_txt = ", ".join(res['sample_works'])
                        st.info(f"Relazione retroattiva {rel_type} creata con {res['total_works']} albi. Esempi: {works_txt}")
                    else:
                        st.info("Nessun albo specificato o corrispondente. L'autore e disponibile per future associazioni.")

    #Editore (Publisher)
    elif create_type == "Editore (Publisher)":
        with st.form("form_create_publisher"):
            col_p1, col_p2 = st.columns(2)
            new_pub_code = col_p1.text_input("Codice identificativo editore (es. IMAGE):", value="IMAGE")
            new_pub_name = col_p2.text_input("Nome completo editore:", value="Image Comics")
            submit_c_pub = st.form_submit_button("Salva Editore")
            
        if submit_c_pub:
            if not new_pub_code.strip() or not new_pub_name.strip():
                st.error("Codice e Nome sono obbligatori.")
            else:
                with driver.session() as session:
                    q_c_pub = """
                        MERGE (p:Publisher {code: $code})
                        SET p.name = $name
                        RETURN p.code AS code, p.name AS name
                    """
                    res = session.run(q_c_pub, code=new_pub_code.strip(), name=new_pub_name.strip()).single()
                    st.success(f"Editore '{res['name']}' ({res['code']}) registrato con successo!")

#Update
with tab_update:
    st.subheader("Aggiornamento Informazioni Record")
    update_type = st.radio("Seleziona l'entita da modificare:", ENTITIES_LIST, horizontal=True, key="rad_update")
    
    #Aggiorna Personaggio
    if update_type == "Personaggio (Character)":
        target_char_id = st.text_input("ID del personaggio da modificare:", value="custom_hero_01")
        col_u1, col_u2 = st.columns(2)
        up_align = col_u1.selectbox("Nuovo Allineamento Morale:", ["Good", "Bad", "Neutral", "Reformed"])
        up_status = col_u2.text_input("Nuovo Stato / Note:", value="Attivo")
        
        if st.button("Aggiorna Personaggio", key="btn_update_char"):
            with driver.session() as session:
                q_up_c = """
                    MATCH (c:Character {id: $id})
                    SET c.alignment = $alignment,
                        c.status = $status
                    RETURN c.id AS id, c.name AS name, c.alignment AS alignment, c.status AS status
                """
                res = session.run(q_up_c, id=target_char_id.strip(), alignment=up_align, status=up_status.strip()).single()
                if res:
                    st.success(f"Personaggio '{res['name']}' aggiornato con successo!")
                    st.json(dict(res))
                else:
                    st.error(f"Nessun personaggio trovato con ID '{target_char_id}'.")

    #Aggiorna Albo (Issue)
    elif update_type == "Albo (Issue)":
        target_iss_id = st.text_input("ID dell'albo da modificare:", value="custom_issue_01")
        col_ui1, col_ui2 = st.columns(2)
        up_iss_title = col_ui1.text_input("Nuovo Titolo Albo:")
        up_iss_year = col_ui2.number_input("Nuovo Anno di Pubblicazione:", min_value=1930, max_value=2030, value=2026)
        
        if st.button("Aggiorna Albo", key="btn_update_issue"):
            with driver.session() as session:
                q_up_i = """
                    MATCH (i:Issue {id: $id})
                    SET i.release_year = toInteger($year)
                    WITH i
                    FOREACH (_ IN CASE WHEN $title <> '' THEN [1] ELSE [] END |
                        SET i.title = $title
                    )
                    RETURN i.id AS id, i.title AS title, i.release_year AS release_year
                """
                res = session.run(q_up_i, id=target_iss_id.strip(), title=up_iss_title.strip(), year=up_iss_year).single()
                if res:
                    st.success(f"Albo '{res['title']}' aggiornato correttamente:")
                    st.json(dict(res))
                else:
                    st.error(f"Nessun albo trovato con ID '{target_iss_id}'.")

    #Aggiorna Serie (Series)
    elif update_type == "Serie (Series)":
        target_ser_name = st.text_input("Nome attuale della Serie:")
        new_ser_rename = st.text_input("Nuovo nome della Serie:")
        if st.button("Aggiorna Nome Serie", key="btn_update_ser"):
            if not target_ser_name.strip() or not new_ser_rename.strip():
                st.error("Specificare sia il nome attuale che il nuovo nome.")
            else:
                with driver.session() as session:
                    q_up_s = """
                        MATCH (s:Series {name: $old_name})
                        SET s.name = $new_name
                        RETURN s.name AS name
                    """
                    res = session.run(q_up_s, old_name=target_ser_name.strip(), new_name=new_ser_rename.strip()).single()
                    if res:
                        st.success(f"Serie rinominata in '{res['name']}'!")
                    else:
                        st.error(f"Nessuna serie trovata con nome '{target_ser_name}'.")

    #Aggiorna Autore (Creator)
    elif update_type == "Autore (Creator)":
        target_cr_name = st.text_input("Nome attuale dell'autore:")
        new_cr_rename = st.text_input("Nuovo nome dell'autore:")
        if st.button("Aggiorna Nome Autore", key="btn_update_cr"):
            if not target_cr_name.strip() or not new_cr_rename.strip():
                st.error("Specificare sia il nome attuale che il nuovo nome.")
            else:
                with driver.session() as session:
                    q_up_cr = """
                        MATCH (cr:Creator {name: $old_name})
                        SET cr.name = $new_name
                        RETURN cr.name AS name
                    """
                    res = session.run(q_up_cr, old_name=target_cr_name.strip(), new_name=new_cr_rename.strip()).single()
                    if res:
                        st.success(f"Autore rinominato in '{res['name']}'!")
                    else:
                        st.error(f"Nessun autore trovato con nome '{target_cr_name}'.")

    #Aggiorna Editore (Publisher)
    elif update_type == "Editore (Publisher)":
        target_pub_code = st.text_input("Codice dell'editore da modificare (es. DC, Marvel):", value="DC")
        new_pub_fullname = st.text_input("Nuovo Nome Esteso Editore:", value="DC Comics Entertainment")
        if st.button("Aggiorna Editore", key="btn_update_pub"):
            with driver.session() as session:
                q_up_p = """
                    MATCH (p:Publisher {code: $code})
                    SET p.name = $name
                    RETURN p.code AS code, p.name AS name
                """
                res = session.run(q_up_p, code=target_pub_code.strip(), name=new_pub_fullname.strip()).single()
                if res:
                    st.success(f"Editore '{res['code']}' aggiornato in '{res['name']}'!")
                else:
                    st.error(f"Nessun editore trovato con codice '{target_pub_code}'.")
#Delete
with tab_delete:
    st.subheader("Cancellazione Record")
    delete_type = st.radio("Seleziona l'entita da eliminare:", ENTITIES_LIST, horizontal=True, key="rad_delete")
    
    #Elimina Personaggio
    if delete_type == "Personaggio (Character)":
        del_char_id = st.text_input("ID del personaggio da eliminare:", value="custom_hero_01")
        if st.button("Elimina Personaggio Definitivamente", type="primary", key="btn_del_char"):
            with driver.session() as session:
                q_check = "MATCH (c:Character {id: $id}) RETURN c.name AS name"
                found = session.run(q_check, id=del_char_id.strip()).single()
                if found:
                    q_del = "MATCH (c:Character {id: $id}) DETACH DELETE c"
                    session.run(q_del, id=del_char_id.strip())
                    st.success(f"Il personaggio '{found['name']}' (ID: {del_char_id}) e tutte le sue relazioni sono stati rimossi.")
                else:
                    st.error(f"Nessun personaggio trovato con ID '{del_char_id}'.")

    #Elimina Albo (Issue)
    elif delete_type == "Albo (Issue)":
        del_iss_id = st.text_input("ID dell'albo da eliminare:", value="custom_issue_01")
        if st.button("Elimina Albo Definitivamente", type="primary", key="btn_del_issue"):
            with driver.session() as session:
                q_check_i = "MATCH (i:Issue {id: $id}) RETURN i.title AS title"
                found_i = session.run(q_check_i, id=del_iss_id.strip()).single()
                if found_i:
                    q_del_i = "MATCH (i:Issue {id: $id}) DETACH DELETE i"
                    session.run(q_del_i, id=del_iss_id.strip())
                    st.success(f"L'albo '{found_i['title']}' (ID: {del_iss_id}) e i suoi collegamenti sono stati rimossi.")
                else:
                    st.error(f"Nessun albo trovato con ID '{del_iss_id}'.")

    #Elimina Serie (Series)
    elif delete_type == "Serie (Series)":
        del_ser_name = st.text_input("Nome esatto della serie da eliminare:")
        if st.button("Elimina Serie Definitivamente", type="primary", key="btn_del_ser"):
            with driver.session() as session:
                q_check_s = "MATCH (s:Series {name: $name}) RETURN s.name AS name"
                found_s = session.run(q_check_s, name=del_ser_name.strip()).single()
                if found_s:
                    q_del_s = "MATCH (s:Series {name: $name}) DETACH DELETE s"
                    session.run(q_del_s, name=del_ser_name.strip())
                    st.success(f"La serie '{found_s['name']}' e tutte le sue relazioni sono state rimosse.")
                else:
                    st.error(f"Nessuna serie trovata con nome '{del_ser_name}'.")

    #Elimina Autore (Creator)
    elif delete_type == "Autore (Creator)":
        del_cr_name = st.text_input("Nome esatto dell'autore da eliminare:")
        if st.button("Elimina Autore Definitivamente", type="primary", key="btn_del_cr"):
            with driver.session() as session:
                q_check_c = "MATCH (cr:Creator {name: $name}) RETURN cr.name AS name"
                found_c = session.run(q_check_c, name=del_cr_name.strip()).single()
                if found_c:
                    q_del_c = "MATCH (cr:Creator {name: $name}) DETACH DELETE cr"
                    session.run(q_del_c, name=del_cr_name.strip())
                    st.success(f"L'autore '{found_c['name']}' e le sue relazioni sono stati rimossi.")
                else:
                    st.error(f"Nessun autore trovato con nome '{del_cr_name}'.")

    #Elimina Editore (Publisher)
    elif delete_type == "Editore (Publisher)":
        del_pub_code = st.text_input("Codice editore da eliminare:")
        st.caption("Attenzione: rimuovere un editore principale (DC/Marvel) scolleghera migliaia di record.")
        if st.button("Elimina Editore Definitivamente", type="primary", key="btn_del_pub"):
            with driver.session() as session:
                q_check_p = "MATCH (p:Publisher {code: $code}) RETURN p.name AS name"
                found_p = session.run(q_check_p, code=del_pub_code.strip()).single()
                if found_p:
                    q_del_p = "MATCH (p:Publisher {code: $code}) DETACH DELETE p"
                    session.run(q_del_p, code=del_pub_code.strip())
                    st.success(f"L'editore '{found_p['name']}' ({del_pub_code}) e stato rimosso.")
                else:
                    st.error(f"Nessun editore trovato con codice '{del_pub_code}'.")

#Autori e collaboratori
with tab_join:
    st.subheader("Esplorazione Autori e Opere Collegate")
    st.markdown("Ricerca per entità")
    
    col_j1, col_j2 = st.columns([2, 1])
    author_choice = col_j1.selectbox(
        "Seleziona un autore in catalogo:",
        ["Frank Miller", "Chip Zdarsky", "Marco Checchetto", "Stan Lee", "Jack Kirby", "Chuck Dixon", "Dan Slott"]
    )
    custom_author = col_j2.text_input("Oppure cerca per nome:")
    selected_author = custom_author.strip() if custom_author.strip() else author_choice
    
    if st.button("Mostra Opere Collegate", key="btn_join"):
        with driver.session() as session:
            q_join = """
                MATCH (cr:Creator)-[w:WROTE]->(i:Issue)-[:PART_OF_SERIES]->(s:Series)
                WHERE toLower(cr.name) CONTAINS toLower($author)
                OPTIONAL MATCH (hero:Character)-[:STARS_IN]->(s)
                RETURN i.title AS Albo, 
                       s.name AS Serie, 
                       collect(DISTINCT hero.name) AS Protagonisti, 
                       i.release_year AS Anno
                ORDER BY Anno ASC
                LIMIT 50
            """
            res_join = list(session.run(q_join, author=selected_author))
            
            if res_join:
                st.success(f"Trovati {len(res_join)} albi scritti da {selected_author}:")
                data_table = []
                for r in res_join:
                    protagonisti_str = ", ".join(r["Protagonisti"]) if r["Protagonisti"] else "Non specificato"
                    data_table.append({
                        "Albo": r["Albo"],
                        "Serie": r["Serie"],
                        "Protagonisti": protagonisti_str,
                        "Anno": r["Anno"]
                    })
                st.dataframe(pd.DataFrame(data_table), use_container_width=True)
            else:
                st.warning(f"Nessun albo trovato per l'autore '{selected_author}'.")