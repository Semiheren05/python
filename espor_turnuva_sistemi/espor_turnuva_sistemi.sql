--
-- PostgreSQL database dump
--

-- Dumped from database version 17.0
-- Dumped by pg_dump version 17.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: get_top_players(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_top_players() RETURNS TABLE(username character varying, total_prize numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT u.username, SUM(tr.prize_won) as total_prize
    FROM Users u
    JOIN Teams tm ON u.user_id = tm.leader_id
    JOIN Tournament_Results tr ON tm.team_id = tr.team_id
    GROUP BY u.username
    ORDER BY total_prize DESC
    LIMIT 5;
END;
$$;

ALTER FUNCTION public.get_top_players() OWNER TO postgres;

--
-- Name: get_tournament_stats(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_tournament_stats(p_game_type character varying) RETURNS record
    LANGUAGE plpgsql
    AS $$
DECLARE
    stats RECORD;
    cur CURSOR FOR SELECT COUNT(*) as count, SUM(prize_pool) as total_prize
                  FROM Tournaments WHERE game_type = p_game_type;
BEGIN
    OPEN cur;
    FETCH cur INTO stats;
    CLOSE cur;
    RETURN stats;
END;
$$;

ALTER FUNCTION public.get_tournament_stats(p_game_type character varying) OWNER TO postgres;

--
-- Name: get_user_tournaments(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_tournaments(p_user_id integer) RETURNS TABLE(tournament_id integer, game_type character varying, rank integer)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT t.tournament_id, t.game_type, tr.rank
    FROM Tournaments t
    JOIN Tournament_Results tr ON t.tournament_id = tr.tournament_id
    JOIN Teams tm ON tr.team_id = tm.team_id
    WHERE tm.leader_id = p_user_id;
END;
$$;

ALTER FUNCTION public.get_user_tournaments(p_user_id integer) OWNER TO postgres;

--
-- Name: notify_new_user(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.notify_new_user() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO Trigger_Logs (message) VALUES ('New user registered: ' || NEW.username);
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.notify_new_user() OWNER TO postgres;

--
-- Name: notify_result_update(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.notify_result_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO Trigger_Logs (message) VALUES ('Tournament result updated for team_id: ' || NEW.team_id);
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.notify_result_update() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: teams; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teams (
    team_id integer NOT NULL,
    tournament_id integer,
    team_name character varying(50) NOT NULL,
    leader_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    game_type character varying(50)
);

ALTER TABLE public.teams OWNER TO postgres;

--
-- Name: teams_team_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.teams_team_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.teams_team_id_seq OWNER TO postgres;

--
-- Name: teams_team_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.teams_team_id_seq OWNED BY public.teams.team_id;

--
-- Name: tournament_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tournament_results (
    result_id integer NOT NULL,
    tournament_id integer,
    team_id integer,
    rank integer NOT NULL,
    prize_won numeric(10,2),
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tournament_results_prize_won_check CHECK ((prize_won >= (0)::numeric)),
    CONSTRAINT tournament_results_rank_check CHECK ((rank > 0))
);

ALTER TABLE public.tournament_results OWNER TO postgres;

--
-- Name: tournament_results_result_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tournament_results_result_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.tournament_results_result_id_seq OWNER TO postgres;

--
-- Name: tournament_results_result_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tournament_results_result_id_seq OWNED BY public.tournament_results.result_id;

--
-- Name: tournaments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tournaments (
    tournament_id integer NOT NULL,
    game_type character varying(50) NOT NULL,
    tournament_date date NOT NULL,
    prize_pool numeric(10,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    tournament_name character varying(100),
    CONSTRAINT tournaments_prize_pool_check CHECK ((prize_pool >= (0)::numeric))
);

ALTER TABLE public.tournaments OWNER TO postgres;

--
-- Name: tournaments_tournament_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tournaments_tournament_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.tournaments_tournament_id_seq OWNER TO postgres;

--
-- Name: tournaments_tournament_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tournaments_tournament_id_seq OWNED BY public.tournaments.tournament_id;

--
-- Name: trigger_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.trigger_logs (
    log_id integer NOT NULL,
    message character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.trigger_logs OWNER TO postgres;

--
-- Name: trigger_logs_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.trigger_logs_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.trigger_logs_log_id_seq OWNER TO postgres;

--
-- Name: trigger_logs_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.trigger_logs_log_id_seq OWNED BY public.trigger_logs.log_id;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    favorite_game character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    password text,
    profile_update_time text,
    CONSTRAINT users_favorite_game_check CHECK (((favorite_game)::text = ANY ((ARRAY['Valorant'::character varying, 'League of Legends'::character varying, 'CS:GO'::character varying])::text[])))
);

ALTER TABLE public.users OWNER TO postgres;

--
-- Name: user_tournament_history; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.user_tournament_history AS
 SELECT u.username,
    t.game_type,
    t.tournament_date,
    tr.rank,
    tr.prize_won
   FROM (((public.users u
     JOIN public.teams tm ON ((u.user_id = tm.leader_id)))
     JOIN public.tournament_results tr ON ((tm.team_id = tr.team_id)))
     JOIN public.tournaments t ON ((tr.tournament_id = t.tournament_id)));

ALTER VIEW public.user_tournament_history OWNER TO postgres;

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_user_id_seq OWNER TO postgres;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;

--
-- Name: teams team_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams ALTER COLUMN team_id SET DEFAULT nextval('public.teams_team_id_seq'::regclass);

--
-- Name: tournament_results result_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournament_results ALTER COLUMN result_id SET DEFAULT nextval('public.tournament_results_result_id_seq'::regclass);

--
-- Name: tournaments tournament_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournaments ALTER COLUMN tournament_id SET DEFAULT nextval('public.tournaments_tournament_id_seq'::regclass);

--
-- Name: trigger_logs log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.trigger_logs ALTER COLUMN log_id SET DEFAULT nextval('public.trigger_logs_log_id_seq'::regclass);

--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);

--
-- Data for Name: teams; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.teams (team_id, tournament_id, team_name, leader_id, created_at, game_type) VALUES
(2, 1, 'Team(beta)', 2, '2025-04-29 23:13:15.259702', 'Valorant'),
(3, 2, 'Team(gamma)', 3, '2025-04-29 23:13:15.259702', 'League of Legends'),
(4, 2, 'Team(delta)', 4, '2025-04-29 23:13:15.259702', 'League of Legends'),
(5, 3, 'Team(epsilon)', 5, '2025-04-29 23:13:15.259702', 'CS:GO'),
(6, 3, 'Team(zeta)', 6, '2025-04-29 23:13:15.259702', 'CS:GO'),
(7, 4, 'Team(eta)', 7, '2025-04-29 23:13:15.259702', 'Valorant'),
(8, 4, 'Team(theta)', 8, '2025-04-29 23:13:15.259702', 'Valorant'),
(9, 5, 'Team(iota)', 9, '2025-04-29 23:13:15.259702', 'League of Legends'),
(10, 5, 'Team(kappa)', 10, '2025-04-29 23:13:15.259702', 'League of Legends'),
(11, 12, 'DARKKKK', 12, '2025-05-02 02:15:37.667764', 'CS:GO');

--
-- Data for Name: tournament_results; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.tournament_results (result_id, tournament_id, team_id, rank, prize_won, updated_at) VALUES
(3, 2, 3, 1, 6000.00, '2025-04-29 23:13:15.259702'),
(4, 2, 4, 2, 3000.00, '2025-04-29 23:13:15.259702'),
(5, 3, 5, 1, 4500.00, '2025-04-29 23:13:15.259702'),
(6, 3, 6, 2, 2250.00, '2025-04-29 23:13:15.259702'),
(7, 4, 7, 1, 3600.00, '2025-04-29 23:13:15.259702'),
(8, 4, 8, 2, 1800.00, '2025-04-29 23:13:15.259702'),
(9, 5, 9, 1, 7200.00, '2025-04-29 23:13:15.259702'),
(10, 5, 10, 2, 3600.00, '2025-04-29 23:13:15.259702'),
(2, 1, 2, 2, 100000.00, '2025-04-29 23:13:15.259702');

--
-- Data for Name: tournaments; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.tournaments (tournament_id, game_type, tournament_date, prize_pool, created_at, tournament_name) VALUES
(2, 'League of Legends', '2025-05-10', 10000.00, '2025-04-29 23:13:15.259702', NULL),
(3, 'CS:GO', '2025-05-15', 7500.00, '2025-04-29 23:13:15.259702', NULL),
(4, 'Valorant', '2025-06-01', 6000.00, '2025-04-29 23:13:15.259702', NULL),
(5, 'League of Legends', '2025-06-10', 12000.00, '2025-04-29 23:13:15.259702', NULL),
(1, 'Valorant', '2025-05-01', 8000.00, '2025-04-29 23:13:15.259702', NULL),
(12, 'CS:GO', '2006-01-01', 24000.00, '2025-05-02 01:53:38.508999', 'cscscscs');

--
-- Data for Name: trigger_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.trigger_logs (log_id, message, created_at) VALUES
(1, 'Tournament result updated for team_id: 2', '2025-04-29 23:38:01.689199'),
(2, 'Tournament result updated for team_id: 2', '2025-04-29 23:38:18.189614'),
(3, 'Tournament result updated for team_id: 2', '2025-04-29 23:38:34.273861'),
(4, 'Tournament result updated for team_id: 2', '2025-04-29 23:38:57.03023'),
(5, 'Tournament result updated for team_id: 2', '2025-04-29 23:39:25.801603'),
(6, 'Tournament result updated for team_id: 2', '2025-04-29 23:39:48.698497'),
(7, 'New user registered: test', '2025-04-30 02:13:29.226209'),
(8, 'New user registered: test', '2025-05-02 03:03:03.981393');

--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.users (user_id, username, email, favorite_game, created_at, password, profile_update_time) VALUES
(1, 'player1', 'player1@example.com', 'Valorant', '2025-04-29 23:13:15.259702', NULL, NULL),
(2, 'player2', 'player2@example.com', 'League of Legends', '2025-04-29 23:13:15.259702', NULL, NULL),
(3, 'player3', 'player3@example.com', 'CS:GO', '2025-04-29 23:13:15.259702', NULL, NULL),
(4, 'player4', 'player4@example.com', 'Valorant', '2025-04-29 23:13:15.259702', NULL, NULL),
(5, 'player5', 'player5@example.com', 'League of Legends', '2025-04-29 23:13:15.259702', NULL, NULL),
(6, 'player6', 'player6@example.com', 'CS:GO', '2025-04-29 23:13:15.259702', NULL, NULL),
(7, 'player7', 'player7@example.com', 'Valorant', '2025-04-29 23:13:15.259702', NULL, NULL),
(8, 'player8', 'player8@example.com', 'League of Legends', '2025-04-29 23:13:15.259702', NULL, NULL),
(9, 'player9', 'player9@example.com', 'CS:GO', '2025-04-29 23:13:15.259702', NULL, NULL),
(10, 'player10', 'player10@example.com', 'Valorant', '2025-04-29 23:13:15.259702', NULL, NULL),
(12, 'eco', 'test@example.com', 'Valorant', '2025-04-30 02:13:29.226209', '1', '02.05.2025 02:41'),
(16, 'test', 'test@gmail.com', 'Valorant', '2025-05-02 03:03:03.981393', '1', NULL);

--
-- Name: teams_team_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.teams_team_id_seq', 11, true);

--
-- Name: tournament_results_result_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tournament_results_result_id_seq', 10, true);

--
-- Name: tournaments_tournament_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tournaments_tournament_id_seq', 12, true);

--
-- Name: trigger_logs_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.trigger_logs_log_id_seq', 8, true);

--
-- Name: users_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_user_id_seq', 16, true);

--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);

--
-- Name: tournament_results tournament_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournament_results
    ADD CONSTRAINT tournament_results_pkey PRIMARY KEY (result_id);

--
-- Name: tournaments tournaments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournaments
    ADD CONSTRAINT tournaments_pkey PRIMARY KEY (tournament_id);

--
-- Name: trigger_logs trigger_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.trigger_logs
    ADD CONSTRAINT trigger_logs_pkey PRIMARY KEY (log_id);

--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);

--
-- Name: tournament_results result_updated_trigger; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER result_updated_trigger AFTER UPDATE ON public.tournament_results FOR EACH ROW EXECUTE FUNCTION public.notify_result_update();

--
-- Name: users user_added_trigger; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER user_added_trigger AFTER INSERT ON public.users FOR EACH ROW EXECUTE FUNCTION public.notify_new_user();

--
-- Name: teams teams_leader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_leader_id_fkey FOREIGN KEY (leader_id) REFERENCES public.users(user_id) ON DELETE RESTRICT;

--
-- Name: teams teams_tournament_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_tournament_id_fkey FOREIGN KEY (tournament_id) REFERENCES public.tournaments(tournament_id) ON DELETE RESTRICT;

--
-- Name: tournament_results tournament_results_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournament_results
    ADD CONSTRAINT tournament_results_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id) ON DELETE RESTRICT;

--
-- Name: tournament_results tournament_results_tournament_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tournament_results
    ADD CONSTRAINT tournament_results_tournament_id_fkey FOREIGN KEY (tournament_id) REFERENCES public.tournaments(tournament_id) ON DELETE RESTRICT;

--
-- PostgreSQL database dump complete
--