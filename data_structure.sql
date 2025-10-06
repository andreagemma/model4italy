
/* =====
   settings
   ===== */
CREATE TABLE settings
(
    name        text                  NOT NULL,
    value       text                  NOT NULL,
    
    CONSTRAINT settings_pk PRIMARY KEY (name)
);

COMMENT ON TABLE  settings IS 'Tabella dei modi di trasporto';
COMMENT ON COLUMN settings.name         IS 'Nome del parametro';
COMMENT ON COLUMN settings.value        IS 'Valore del parametro';


/* =====
   modes
   ===== */
CREATE TABLE modes
(
    id          int                   NOT NULL,
    code        varchar(4)            NOT NULL,
    description text                  NOT NULL,
    eq_factor   double precision      NOT NULL DEFAULT 1,
    
    CONSTRAINT modes_pk PRIMARY KEY (id),
    CONSTRAINT modes_unique UNIQUE (code)
);

COMMENT ON TABLE  modes IS 'Tabella dei modi di trasporto';
COMMENT ON COLUMN modes.id          IS 'Identificativo del modo.';
COMMENT ON COLUMN modes.code        IS 'Codice del modo (es: c, h, all, null, ...)';
COMMENT ON COLUMN modes.description IS 'Descrizione del modo (es: Car, Heavy, All Modes, No Modes, ...).';
COMMENT ON COLUMN modes.eq_factor   IS 'Fattore di equivalenza del modo.';

/* =====
   nodes
   ===== */
CREATE TABLE nodes
(
    id          bigint                NOT NULL,
    centroid    smallint              NOT NULL,
    modes       text                  NULL,
    geometry    geometry(Point, 4326) NOT NULL,

    CONSTRAINT nodes_pk PRIMARY KEY (id)
);

CREATE INDEX nodes_geom_gist ON nodes USING GIST (geom);


COMMENT ON TABLE  nodes IS 'Nodi della rete, inclusi eventuali centroidi di zona.';
COMMENT ON COLUMN nodes.id          IS 'Identificativo del nodo.';
COMMENT ON COLUMN nodes.centroid    IS 'Indicatore di centroide, 1 se il nodo è un centroide di zona.';
COMMENT ON COLUMN nodes.modes       IS 'Modalità associate al nodo, formato stringa breve.';
COMMENT ON COLUMN nodes.geom        IS 'Geometria del nodo come POINT in WGS84.';

/* =====
   links
   ===== */
CREATE TABLE links
(
    id          bigint                           NOT NULL,
    from_node   bigint                           NOT NULL,
    to_node     bigint                           NOT NULL,
    name        text                             NOT NULL DEFAULT '',
    length      double precision                 NOT NULL,
    v0          double precision                 NOT NULL,
    connector   smallint                         NOT NULL,
    lanes       double precision                 NOT NULL,
    alpha       double precision                 NOT NULL,
    rcr         double precision                 NOT NULL,
    capacity    double precision                 NOT NULL,
    modes       text                             NULL,    
    geometry    geometry(MultiLineString, 4326)  NOT NULL,

    CONSTRAINT links_pk PRIMARY KEY (id)
);

CREATE INDEX links_geom_gist ON links USING GIST (geom);
ALTER TABLE links ADD CONSTRAINT links_unique UNIQUE (from_node,to_node);


COMMENT ON TABLE  links IS 'Archi della rete stradale con attributi geometrici e operativi.';
COMMENT ON COLUMN links.id          IS 'Identificativo univoco dell’arco.';
COMMENT ON COLUMN links.from_node   IS 'Nodo iniziale dell’arco.';
COMMENT ON COLUMN links.to_node     IS 'Nodo finale dell’arco.';
COMMENT ON COLUMN links.name        IS 'Toponimo della strada.';
COMMENT ON COLUMN links.length      IS 'Lunghezza dell’arco in km.';
COMMENT ON COLUMN links.v0          IS 'Velocità a vuoto, tipicamente velocità libera.';
COMMENT ON COLUMN links.connector   IS 'Indicatore di connettore, 1 se connettore, 0 altrimenti.';
COMMENT ON COLUMN links.lanes       IS 'Numero di corsie.';
COMMENT ON COLUMN links.alpha       IS 'Parametro alfa del modello di costo.';
COMMENT ON COLUMN links.rcr         IS 'Parametro di densità critica.';
COMMENT ON COLUMN links.capacity    IS 'Capacità dell’arco.';
COMMENT ON COLUMN links.modes       IS 'Modalità ammesse, ad esempio c, h.';
COMMENT ON COLUMN links.geom        IS 'Geometria dell’arco come MULTILINESTRING in WGS84.';

/* =========
   detectors
   ========= */
CREATE TABLE detectors
(
    id           bigint                           NOT NULL,
    id_link      bigint                           NOT NULL,
    geometr      geometry(MultiLineString, 4326)  NOT NULL,

    CONSTRAINT detectors_pk PRIMARY KEY (id)
);

CREATE INDEX detectors_geom_gist ON detectors USING GIST (geom);

COMMENT ON TABLE  detectors IS 'Tratti o posizioni di rilevazione associati ai link.';
COMMENT ON COLUMN detectors.id          IS 'Identificativo del rilevatore o segmento di rilevazione.';
COMMENT ON COLUMN detectors.id_link     IS 'Identificativo del link associato al rilevatore.';
COMMENT ON COLUMN detectors.geom        IS 'Geometria del tratto di rilevazione, MULTILINESTRING WGS84.';

/* =====
   zones
   ===== */
CREATE TABLE zones
(    
    id           bigint                       NOT NULL,
    geometry     geometry(MultiPolygon, 4326) NOT NULL,

    CONSTRAINT zones_pk PRIMARY KEY (id)
);

CREATE INDEX zones_geom_gist ON zones USING GIST (geom);

COMMENT ON TABLE  zones IS 'Zone di traffico o aree di aggregazione territoriale.';
COMMENT ON COLUMN zones.id          IS 'Identificativo della zona.';
COMMENT ON COLUMN zones.geom        IS 'Geometria della zona come MULTIPOLYGON in WGS84.';


/* =============
   traffic_lights
   ============= */
CREATE TABLE traffic_lights
(
    id           bigserial             NOT NULL,
    cycle        double precision      NOT NULL,
    "offset"     double precision      NOT NULL,
    phases       text                  NOT NULL DEFAULT '{}',
    geom         geometry(Point, 4326) NOT NULL,
    
    CONSTRAINT traffic_lights_pk PRIMARY KEY (id)
);

CREATE INDEX tl_geom_gist ON traffic_lights USING GIST (geom);

COMMENT ON TABLE  traffic_lights IS 'Impianti semaforici con parametri di ciclo e fasi.';
COMMENT ON COLUMN traffic_lights.id          IS 'Identificativo dell’impianto semaforico.';
COMMENT ON COLUMN traffic_lights.cycle       IS 'Durata del ciclo semaforico.';
COMMENT ON COLUMN traffic_lights."offset"    IS 'Offset del ciclo rispetto al riferimento.';
COMMENT ON COLUMN traffic_lights.phases      IS 'Descrizione delle fasi, JSON come testo.';
COMMENT ON COLUMN traffic_lights.geom        IS 'Posizione dell’impianto come POINT in WGS84.';

/* =====
   turns
   ===== */
CREATE TABLE turns
(
    id        bigserial        NOT NULL,
    from_node bigint           NOT NULL,
    via_node  bigint           NOT NULL,
    to_node   bigint           NOT NULL,
    modes     text             NOT NULL,
    penalty   double precision NULL,
    CONSTRAINT turns_pk PRIMARY KEY (id)
);
-- Unicità logica della manovra
CREATE UNIQUE INDEX IF NOT EXISTS turns_unique_from_via_to_modes
    ON turns (from_node, via_node, to_node, modes);

COMMENT ON TABLE  turns IS 'Penalità di manovra tra archi.';
COMMENT ON COLUMN turns.id        IS 'Identificativo di manovra.';
COMMENT ON COLUMN turns.from_node IS 'Nodo di provenienza della manovra.';
COMMENT ON COLUMN turns.via_node  IS 'Nodo intermedio o confluenza della manovra.';
COMMENT ON COLUMN turns.to_node   IS 'Nodo di destinazione della manovra.';
COMMENT ON COLUMN turns.modes     IS 'Modalità coinvolte nelle penalità di manovra.';
COMMENT ON COLUMN turns.penalty   IS 'Penalità associata alla manovra.';

/* ==========
   links_sets
   ========== */
CREATE TABLE links_sets
(
    id           bigserial NOT NULL,
    id_set       varchar   NOT NULL,
    id_link      bigint    NOT NULL,    
    
    CONSTRAINT links_sets_pk PRIMARY KEY (id),
    CONSTRAINT links_set_unique UNIQUE (id_set, id_link)
);

COMMENT ON TABLE  links_sets IS 'Insiemi logici di archi della rete, utili per eventi o analisi.';
COMMENT ON COLUMN links_sets.id          IS 'Identificativo di record.';
COMMENT ON COLUMN links_sets.id_set      IS 'Identificativo dell’insieme di archi.';
COMMENT ON COLUMN links_sets.id_link     IS 'Identificativo dell’arco contenuto nell’insieme.';

/* ======
   events
   ====== */
CREATE TABLE events
(
    id           bigserial NOT NULL,
    id_link_set  text      NULL,
    "type"       text      NULL,
    "start"      text      NULL,
    "end"        text      NULL,
    params       text      NULL DEFAULT '{}',

    CONSTRAINT events_pk PRIMARY KEY (id)
);

/* ======
   alerts
   ====== */
CREATE TABLE alerts
(
    id           bigserial NOT NULL,
    "type"       text      NOT NULL,
    "info"       text      NOT NULL,
    geojson      text      NULL,

    CONSTRAINT alerts_pk PRIMARY KEY (id)
);

COMMENT ON TABLE  alerts IS 'Segnalazioni inviate dal motore di calcolo';
COMMENT ON COLUMN alerts.id          IS 'Identificativo del record';
COMMENT ON COLUMN alerts."type"      IS 'Tipo di segnalazione';
COMMENT ON COLUMN alerts."info"      IS 'Informazioni sulla segnalazione in formato JSON';
COMMENT ON COLUMN events."geojson"   IS 'Geometria di riferimento per la segnalazione in formato JSON (se esistente)';


/* =======
   matrices
   ======= */
CREATE TABLE matrices
(
    id          bigserial        NOT NULL,
    o           bigint NOT NULL,
    d           bigint  NOT NULL,
    value       double precision NOT NULL,
    "timestamp" bigint           NOT NULL,
    mode        varchar(4)       NOT NULL,

    CONSTRAINT matrices_pk PRIMARY KEY (id),
    CONSTRAINT matrices_key UNIQUE (o, d, "timestamp", mode)
);

CREATE INDEX matrices_t_idx  ON matrices (mode, "timestamp");

COMMENT ON TABLE  matrices IS 'Matrice OD, valori su intervalli temporali.';
COMMENT ON COLUMN matrices.o            IS 'Origine della coppia OD, indice o codice zona.';
COMMENT ON COLUMN matrices.d            IS 'Destinazione della coppia OD, indice o codice zona.';
COMMENT ON COLUMN matrices.value        IS 'Valore della domanda tra O e D nel periodo.';
COMMENT ON COLUMN matrices."timestamp"  IS 'Indice temporale del periodo di domanda.';
COMMENT ON COLUMN matrices.mode         IS 'Modalità di trasporto associata alla domanda.';

/* ======
   counts
   ====== */
CREATE TABLE counts
(
    id          bigserial           NOT NULL,
    id_detector bigint              NOT NULL,
    "timestamp" bigint              NOT NULL,
    mode        varchar(4)          NOT NULL,
    counts      double precision    NULL,

    CONSTRAINT counts_pk PRIMARY KEY (id, "timestamp", mode)
);

CREATE INDEX counts_id_t_idx ON counts (id, "timestamp");

COMMENT ON TABLE  counts IS 'Conteggi osservati dai detectors per ogni intervallo temporali.';
COMMENT ON COLUMN counts.id           IS 'Identificativo del record.';
COMMENT ON COLUMN counts.id_detector  IS 'Identificativo del detector a cui il conteggio si riferisce.';
COMMENT ON COLUMN counts."timestamp"  IS 'Indice temporale del conteggio.';
COMMENT ON COLUMN counts.mode         IS 'Modalità del conteggio, ad esempio all, c, h.';
COMMENT ON COLUMN counts.counts       IS 'Valore del conteggio nel periodo indicato.';
/* ================================
   last_results
   ================================ */

CREATE TABLE last_results
(
	id        bigserial                   NOT NULL,
    time      timestamp without time zone NOT NULL,
    mode      varchar(4)                  NULL,
    id_link   bigint                      NOT NULL,
    flow_in   double precision            NOT NULL,
    flow_out  double precision            NOT NULL,
    max_q     double precision            NOT NULL,
    mov_vehs  double precision            NOT NULL,
    que_vehs  double precision            NOT NULL,
    speed     double precision            NOT NULL,
    density   double precision            NOT NULL,
    tt        double precision            NOT NULL,
    q_length  double precision            NOT NULL,
    t         bigint                      NOT NULL,
    geometry  geometry(MultiLineString, 4326),

    CONSTRAINT last_results_pk
        PRIMARY KEY (id),
    CONSTRAINT last_results_unique
        UNIQUE (time, mode, id_link)

);

-- Commenti utili per documentazione
COMMENT ON TABLE  last_results          IS 'Risultati aggregati rete, finestra 5 minuti. Risultati sovrascritti ad ogni simulazione';
COMMENT ON COLUMN last_results.time     IS 'Timestamp dell''aggregazione, passi da 5 minuti.';
COMMENT ON COLUMN last_results.mode     IS 'Modalità/segmento: all, c, h, etc..';
COMMENT ON COLUMN last_results.id       IS 'Identificativo link della rete.';
COMMENT ON COLUMN last_results.flow_in  IS 'Flusso in ingresso nell''arco nell''intervallo.';
COMMENT ON COLUMN last_results.flow_out IS 'Flusso in uscita nell''intervallo.';
COMMENT ON COLUMN last_results.max_q    IS 'Coda massima (in veicoli complessivi).';
COMMENT ON COLUMN last_results.mov_vehs IS 'Veicoli in movimento stimati nell link.';
COMMENT ON COLUMN last_results.que_vehs IS 'Veicoli in coda medi.';
COMMENT ON COLUMN last_results.speed    IS 'Velocità media.';
COMMENT ON COLUMN last_results.density  IS 'Densità media.';
COMMENT ON COLUMN last_results.tt       IS 'Tempo di percorrenza medio.';
COMMENT ON COLUMN last_results.q_length IS 'Lunghezza di coda in percentuale.';
COMMENT ON COLUMN last_results.t        IS 'Indice temporale numerico espresso in minuti (ora sono i minuti dalla mezzanotte).';
COMMENT ON COLUMN last_results.geometry IS 'Geometria del link';

/* ================================
   fcd  (Floating Car Data – raw points)
   ================================ */
CREATE TABLE fcd
(
    id_fcd    varchar(40)                   NOT NULL,
    id_veh    varchar(40)                   NOT NULL,
    heading   integer                       NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    engine    smallint                      NOT NULL, 
    speed     real                          NOT NULL,
    lon       double precision              NOT NULL,
    lat       double precision              NOT NULL,

    CONSTRAINT fcd_pk PRIMARY KEY (id_fcd)
);

-- Indici utili
CREATE INDEX IF NOT EXISTS fcd_ts_idx      ON fcd ("timestamp");
CREATE INDEX IF NOT EXISTS fcd_veh_ts_idx  ON fcd (id_veh, "timestamp");

COMMENT ON TABLE  fcd IS 'Floating Car Data: punti GPS grezzi.';
COMMENT ON COLUMN fcd.id_fcd     IS 'Identificativo univoco della misura FCD.';
COMMENT ON COLUMN fcd.id_veh     IS 'Identificativo del veicolo (interno o targa anonimizzata).';
COMMENT ON COLUMN fcd.heading    IS 'Intestazione bussola (gradi 0-359).';
COMMENT ON COLUMN fcd."timestamp"IS 'Tempo di rilevazione in UTC (senza fuso).';
COMMENT ON COLUMN fcd.engine     IS 'Stato motore (0=engine_on/1=moving/2=engine_off).';
COMMENT ON COLUMN fcd.speed      IS 'Velocità istantanea in km/h.';
COMMENT ON COLUMN fcd.lon        IS 'Longitudine WGS84.';
COMMENT ON COLUMN fcd.lat        IS 'Latitudine WGS84.';


/* ================================
   fcd_paths  
   Percorsi osservati
   ================================ */
CREATE TABLE fcd_paths
(
    id          bigserial                  NOT NULL,
    source      bigint                     NOT NULL,
    target      bigint                     NOT NULL,
    mode        varchar(4)                 NOT NULL,
    tot_cost    double precision           NOT NULL,
    links       text                       NOT NULL, -- sequenza di link 
    n_paths     integer                    NOT NULL,
    geometry    geometry(MultiLineString, 4326),

    CONSTRAINT fcd_paths_pk PRIMARY KEY (id),
    CONSTRAINT fcd_paths_unique UNIQUE (source, target, mode)
);

CREATE INDEX IF NOT EXISTS fcd_paths_src_tgt_idx ON fcd_paths (source, target);
CREATE INDEX IF NOT EXISTS fcd_paths_geom_gist   ON fcd_paths USING GIST (geometry);

COMMENT ON TABLE  fcd_paths IS 'Percorsi osservati per origine-destinazione e intervallo temporale.';
COMMENT ON COLUMN fcd_paths.source    IS 'Nodo origine.';
COMMENT ON COLUMN fcd_paths.target    IS 'Nodo destinazione.';
COMMENT ON COLUMN fcd_paths.mode      IS 'Modo (es. c, h, all, …).';
COMMENT ON COLUMN fcd_paths.tot_cost  IS 'Costo medio totale del percorso (minuti).';
COMMENT ON COLUMN fcd_paths.links     IS 'Lista ordinata di ID arco (testo).';
COMMENT ON COLUMN fcd_paths.geometry  IS 'Geometria del percorso come MULTILINESTRING (WGS84).';


/* ================================
   fcd_paths  (path_5_sample.csv)
   Percorsi k-shortest/assegnazione, con geometria WKB (MultiLineString)
   ================================ */
CREATE TABLE paths
(
    id          bigserial                  NOT NULL,
    source      bigint                     NOT NULL,
    target      bigint                     NOT NULL,
    t_start     bigint                     NOT NULL,
    t_base      bigint                     NOT NULL,
    t           bigint                     NOT NULL,
    mode        varchar(4)                 NOT NULL,
    tot_cost    double precision           NOT NULL,
    links       text                       NOT NULL,
    k           integer                    NOT NULL,
    path_flow   double precision           NOT NULL,
    geometry    geometry(MultiLineString, 4326),
    
    CONSTRAINT paths_pk PRIMARY KEY (id),
    CONSTRAINT paths_key UNIQUE (source, target, t_start, t_base, t, mode, k)
);

CREATE INDEX IF NOT EXISTS fcd_paths_geom_gist   ON fcd_paths USING GIST (geometry);

COMMENT ON TABLE  paths IS 'Percorsi (di assegnazione) per origine-destinazione e intervallo temporale.';
COMMENT ON COLUMN paths.source    IS 'Nodo origine.';
COMMENT ON COLUMN paths.target    IS 'Nodo destinazione.';
COMMENT ON COLUMN paths.t_start   IS 'Istante di inizio validità del cammino (minuti) rispetto al t_base.';
COMMENT ON COLUMN paths.t_base    IS 'T “base” (minuti), del modello di simulazione.';
COMMENT ON COLUMN paths.t         IS 'Istante di inizio validità del cammino (minuti).';
COMMENT ON COLUMN paths.mode      IS 'Modo (es. c, h, all, …).';
COMMENT ON COLUMN paths.tot_cost  IS 'Costo totale del percorso.';
COMMENT ON COLUMN paths.links     IS 'Lista ordinata di ID arco (testo).';
COMMENT ON COLUMN paths.k         IS 'Indice del percorso nella famiglia k-shortest.';
COMMENT ON COLUMN paths.path_flow IS 'Flusso assegnato al percorso.';
COMMENT ON COLUMN paths.geometry  IS 'Geometria del percorso come MULTILINESTRING (WGS84).';

/* ================================
   fcd_graph  
   Statistiche per link calcolate da fcd
   ================================ */
CREATE TABLE fcd_graph
(
    id         bigserial    NOT NULL,
    id_link    bigint       NOT NULL,      -- id link
    fcd_n      text         NOT NULL,      -- array di conteggi per bin, formattato come stringa es. "[4 6 3 …]"
    fcd_speed  text         NOT NULL,      -- array di velocità per bin, come stringa
    mode       varchar(8)   NOT NULL,      -- es. 'wa'
    day_type   varchar(16)  NOT NULL,      -- es. 'friday','saturday','sunday'
    t_base     integer      NOT NULL,      -- base temporale (minuti)

    CONSTRAINT fcd_graph_pk PRIMARY KEY (id),
    CONSTRAINT fcd_graph_unique UNIQUE (id_link, mode, day_type, t_base)
);

CREATE INDEX IF NOT EXISTS fcd_graph_mode_day_idx ON fcd_graph (mode, day_type, t_base);

COMMENT ON TABLE  fcd_graph IS 'Statistiche FCD per link e tipologia giorno: conteggi e velocità per bin temporali.';
COMMENT ON COLUMN fcd_graph.id        IS 'Identificativo di record link.';
COMMENT ON COLUMN fcd_graph.id_link   IS 'Identificativo del link.';
COMMENT ON COLUMN fcd_graph.fcd_n     IS 'Array come testo dei conteggi per bin temporali (15 min).';
COMMENT ON COLUMN fcd_graph.fcd_speed IS 'Array come testo delle velocità per bin temporali (15 min).';
COMMENT ON COLUMN fcd_graph.mode      IS 'Modo o scenario FCD (es. wa).';
COMMENT ON COLUMN fcd_graph.day_type  IS 'Tipo di giorno (es: weekday/weekend oppure giorno specifico).';
COMMENT ON COLUMN fcd_graph.t_base    IS 'Istante di validità.';


-- ==========================================
-- Foreign keys richieste
-- ==========================================

-- links.from_node -> nodes.id, links.to_node -> nodes.id
ALTER TABLE links
    ADD CONSTRAINT fk_links_from_node
        FOREIGN KEY (from_node) REFERENCES nodes(id),
    ADD CONSTRAINT fk_links_to_node
        FOREIGN KEY (to_node)   REFERENCES nodes(id);

-- detectors.id_link -> links.id
ALTER TABLE detectors
    ADD CONSTRAINT fk_detectors_id_link
        FOREIGN KEY (id_link) REFERENCES links(id);

-- zones.id -> nodes.id
ALTER TABLE zones
    ADD CONSTRAINT fk_zones_id_node
        FOREIGN KEY (id) REFERENCES nodes(id);

-- turns.* -> nodes.id
ALTER TABLE turns
    ADD CONSTRAINT fk_turns_from_node
        FOREIGN KEY (from_node) REFERENCES nodes(id),
    ADD CONSTRAINT fk_turns_via_node
        FOREIGN KEY (via_node)  REFERENCES nodes(id),
    ADD CONSTRAINT fk_turns_to_node
        FOREIGN KEY (to_node)   REFERENCES nodes(id);

-- links_sets.id_link -> links.id
ALTER TABLE links_sets
    ADD CONSTRAINT fk_links_sets_id_link
        FOREIGN KEY (id_link) REFERENCES links(id);

-- matrices.o, matrices.d -> zones.id
ALTER TABLE matrices
    ADD CONSTRAINT fk_matrices_o_zone
        FOREIGN KEY (o) REFERENCES zones(id),
    ADD CONSTRAINT fk_matrices_d_zone
        FOREIGN KEY (d) REFERENCES zones(id);

-- counts.id_detector -> detectors.id
ALTER TABLE counts
    ADD CONSTRAINT fk_counts_id_detector
        FOREIGN KEY (id_detector) REFERENCES detectors(id);

-- last_results.id_link -> links.id
ALTER TABLE last_results
    ADD CONSTRAINT fk_last_results_id_link
        FOREIGN KEY (id_link) REFERENCES links(id);

-- fcd_graph.id_link -> links.id
ALTER TABLE fcd_graph
    ADD CONSTRAINT fk_fcd_graph_id_link
        FOREIGN KEY (id_link) REFERENCES links(id);        