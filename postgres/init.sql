-- 1. Sicherstellen, dass wir in der richtigen Datenbank arbeiten
\c robot_analytics;

-- 2. pg_cron Erweiterung im System aktivieren
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 3. Tabelle manuell vorab erstellen (Zwingt die Spalte auf echte Zeitzonen!)
CREATE TABLE IF NOT EXISTS topic_events (
    tag  TEXT,
    time TIMESTAMPTZ, -- Weltreisetauglich mit Zeitzone (UTC-fokussiert)
    data JSONB
);

-- 4. Indizes für maximale Performance in Metabase anlegen
CREATE INDEX IF NOT EXISTS idx_topic_events_tag ON topic_events (tag);
CREATE INDEX IF NOT EXISTS idx_topic_events_time ON topic_events (time DESC);
CREATE INDEX IF NOT EXISTS idx_topic_events_run_id ON topic_events ((data->>'run_id'));

-- 5. Der stündliche Storage-Manager (Löscht nach 30 Tagen ODER bei > 150 GB)
SELECT cron.schedule('robot_storage_cleanup', '0 * * * *', $$
BEGIN
    -- Regel A: Lösche Daten, die älter als 30 Tage sind
    DELETE FROM topic_events WHERE time < NOW() - INTERVAL '30 days';

    -- Regel B: Schutz vor voller Festplatte (Limit auf 150 GB)
    IF pg_total_relation_size('topic_events') > (150 * 1024 * 1024 * 1024) THEN
        DELETE FROM topic_events 
        WHERE ctid IN (
            SELECT ctid FROM topic_events 
            ORDER BY time ASC 
            LIMIT (SELECT COUNT(*) / 10 FROM topic_events)
        );
    END IF;
END;
$$);

SELECT cron.schedule('robot_storage_vacuum', '5 * * * *', 'VACUUM topic_events;');