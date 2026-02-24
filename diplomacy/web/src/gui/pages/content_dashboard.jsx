import React from "react";
import {Helmet} from "react-helmet";
import {PageContext} from "../components/page_context";
import {api} from "../utils/api";

// Neon-tinted power colors for dark theme
const POWER_COLORS = {
    AUSTRIA: '#ff4444',
    ENGLAND: '#4488ff',
    FRANCE: '#00ccff',
    GERMANY: '#aaaaaa',
    ITALY: '#44dd44',
    RUSSIA: '#cc66ff',
    TURKEY: '#ffcc00',
};

const POWER_GLOWS = {
    AUSTRIA: 'rgba(255,68,68,0.3)',
    ENGLAND: 'rgba(68,136,255,0.3)',
    FRANCE: 'rgba(0,204,255,0.3)',
    GERMANY: 'rgba(170,170,170,0.2)',
    ITALY: 'rgba(68,221,68,0.3)',
    RUSSIA: 'rgba(204,102,255,0.3)',
    TURKEY: 'rgba(255,204,0,0.3)',
};

function StatusBadge({status}) {
    const styles = {
        forming: {bg: '#334', color: '#88aacc', border: '#556'},
        active: {bg: '#143', color: '#4f8', border: '#2a5'},
        paused: {bg: '#443', color: '#cc8', border: '#665'},
        completed: {bg: '#224', color: '#8af', border: '#449'},
        canceled: {bg: '#322', color: '#966', border: '#544'},
    };
    const s = styles[status] || {bg: '#333', color: '#888', border: '#555'};
    return (
        <span className="dash-status" style={{
            background: s.bg, color: s.color, border: `1px solid ${s.border}`
        }}>
            {status}
        </span>
    );
}

function LiveDot() {
    return <span className="dash-live-dot" title="Auto-refreshing" />;
}

// ─── Phase Timeline ──────────────────────────────────────────

function PhaseTimeline({phases, currentPhase, onSelect, selectedPhase}) {
    if (!phases || phases.length === 0) return null;
    const allPhases = [...phases.map(p => p.name || '?')];
    if (currentPhase && !allPhases.includes(currentPhase)) {
        allPhases.push(currentPhase);
    }
    return (
        <div className="dash-timeline">
            <div className="dash-timeline-track">
                {allPhases.map((name, i) => {
                    const isCurrent = name === currentPhase;
                    const isSelected = name === selectedPhase;
                    const isHistory = phases.some(p => p.name === name);
                    return (
                        <div key={name}
                             className={`dash-timeline-node ${isCurrent ? 'current' : ''} ${isSelected ? 'selected' : ''} ${isHistory ? 'has-data' : ''}`}
                             onClick={() => isHistory && onSelect && onSelect(name)}>
                            <div className="dash-timeline-dot" />
                            <div className="dash-timeline-label">{name}</div>
                            {i < allPhases.length - 1 && <div className="dash-timeline-line" />}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Games Tab ───────────────────────────────────────────────

class GamesPanel extends React.Component {
    constructor(props) {
        super(props);
        this.state = {games: [], loading: true, error: null};
    }

    componentDidMount() {
        this.refresh();
    }

    refresh() {
        this.setState({loading: true, error: null});
        api.listGames()
            .then(data => this.setState({games: data.games || [], loading: false}))
            .catch(e => this.setState({error: e.message, loading: false}));
    }

    render() {
        const {games, loading, error} = this.state;
        return (
            <div className="dash-section">
                <div className="dash-toolbar">
                    <span className="dash-toolbar-info">{games.length} game(s) on server</span>
                    <button className="dash-btn" onClick={() => this.refresh()}>Refresh</button>
                </div>
                {error && <div className="dash-error">{error}</div>}
                {loading && <div className="dash-loading"><div className="dash-spinner" />Loading...</div>}
                {!loading && games.length === 0 && (
                    <div className="dash-empty">No games found. Create one to get started.</div>
                )}
                <div className="dash-games-grid">
                    {games.map(g => (
                        <div key={g.game_id} className="dash-game-card"
                             onClick={() => this.props.onSelectGame(g.game_id)}>
                            <div className="dash-game-card-top">
                                <span className="dash-game-id">{g.game_id}</span>
                                <StatusBadge status={g.status}/>
                            </div>
                            <div className="dash-game-phase">{g.phase}</div>
                            <div className="dash-game-meta">
                                <span>{g.map_name}</span>
                                <span className="dash-game-players">
                                    <span className="dash-game-players-count">{g.n_players}</span>/{g.n_controls}
                                </span>
                                {g.deadline > 0 && <span>{g.deadline}s</span>}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }
}

// ─── Game Detail Tab ─────────────────────────────────────────

class GameDetailPanel extends React.Component {
    constructor(props) {
        super(props);
        this.state = {game: null, history: [], loading: true, error: null, selectedPhase: null};
        this._interval = null;
    }

    componentDidMount() {
        this.refresh();
        this._interval = setInterval(() => this.refresh(), 3000);
    }

    componentWillUnmount() {
        if (this._interval) clearInterval(this._interval);
    }

    componentDidUpdate(prevProps) {
        if (prevProps.gameId !== this.props.gameId) {
            this.setState({game: null, history: [], loading: true, selectedPhase: null});
            this.refresh();
        }
    }

    refresh() {
        if (!this.props.gameId) return;
        Promise.all([
            api.getGame(this.props.gameId),
            api.getHistory(this.props.gameId).catch(() => ({phases: []})),
        ]).then(([gameData, histData]) => {
            this.setState({
                game: gameData,
                history: histData.phases || [],
                loading: false,
                error: null,
            });
        }).catch(e => this.setState({error: e.message, loading: false}));
    }

    onProcess() {
        this.setState({error: null});
        api.processGame(this.props.gameId)
            .then(() => this.refresh())
            .catch(e => this.setState({error: e.message}));
    }

    onDelete() {
        if (!window.confirm(`Delete game "${this.props.gameId}"?`)) return;
        api.deleteGame(this.props.gameId)
            .then(() => this.props.onBack())
            .catch(e => this.setState({error: e.message}));
    }

    render() {
        const {game, history, loading, error, selectedPhase} = this.state;
        if (!this.props.gameId) {
            return <div className="dash-empty">Select a game from the Games tab.</div>;
        }
        if (loading && !game) return <div className="dash-loading"><div className="dash-spinner" />Loading...</div>;
        if (error && !game) return <div className="dash-error">{error}</div>;
        if (!game) return null;

        const powers = game.powers || {};
        const powerNames = Object.keys(powers).sort(
            (a, b) => (powers[b].centers || []).length - (powers[a].centers || []).length
        );

        // Phase detail from history
        const phaseDetail = selectedPhase
            ? history.find(p => p.name === selectedPhase)
            : null;

        return (
            <div className="dash-section">
                {error && <div className="dash-error">{error}</div>}

                {/* Header bar */}
                <div className="dash-detail-header">
                    <div className="dash-detail-left">
                        <button className="dash-btn dash-btn-ghost" onClick={this.props.onBack}>&larr; Back</button>
                        <span className="dash-detail-title">{game.game_id}</span>
                        <StatusBadge status={game.status}/>
                        <LiveDot />
                    </div>
                    <div className="dash-detail-right">
                        {!game.is_done && (
                            <button className="dash-btn dash-btn-warn" onClick={() => this.onProcess()}>
                                Force Process
                            </button>
                        )}
                        <button className="dash-btn dash-btn-danger" onClick={() => this.onDelete()}>
                            Delete
                        </button>
                    </div>
                </div>

                {/* Current phase display */}
                <div className="dash-phase-display">
                    <span className="dash-phase-current">{game.phase}</span>
                    <span className="dash-phase-map">{game.map_name}</span>
                    {game.is_done && <span className="dash-phase-done">GAME OVER</span>}
                </div>

                {/* Phase timeline */}
                <PhaseTimeline
                    phases={history}
                    currentPhase={game.phase}
                    selectedPhase={selectedPhase}
                    onSelect={(name) => this.setState({selectedPhase: selectedPhase === name ? null : name})}
                />

                {/* Selected phase detail */}
                {phaseDetail && (
                    <div className="dash-phase-detail">
                        <div className="dash-phase-detail-title">
                            {phaseDetail.name}
                            <button className="dash-btn dash-btn-ghost dash-btn-xs"
                                    onClick={() => this.setState({selectedPhase: null})}>
                                Close
                            </button>
                        </div>
                        <div className="dash-phase-orders-grid">
                            {Object.keys(phaseDetail.orders || {}).sort().map(pwr => {
                                const color = POWER_COLORS[pwr] || '#888';
                                const pwrOrders = (phaseDetail.orders || {})[pwr] || [];
                                const pwrResults = (phaseDetail.results || {})[pwr] || [];
                                return (
                                    <div key={pwr} className="dash-phase-power-orders">
                                        <div className="dash-phase-power-name" style={{color}}>{pwr}</div>
                                        {pwrOrders.map((order, oi) => {
                                            const result = pwrResults[oi];
                                            const ok = result !== undefined && (!result || result.length === 0);
                                            return (
                                                <div key={oi} className="dash-phase-order-line">
                                                    <span className="dash-phase-order-text">{order}</span>
                                                    <span className={ok ? 'dash-result-ok' : 'dash-result-fail'}>
                                                        {result !== undefined ? (ok ? 'OK' : result.join(',')) : ''}
                                                    </span>
                                                </div>
                                            );
                                        })}
                                        {pwrOrders.length === 0 && (
                                            <div className="dash-phase-no-orders">no orders</div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Power cards */}
                <div className="dash-powers-grid">
                    {powerNames.map(pwr => {
                        const p = powers[pwr];
                        const color = POWER_COLORS[pwr] || '#888';
                        const glow = POWER_GLOWS[pwr] || 'rgba(128,128,128,0.2)';
                        const nCenters = (p.centers || []).length;
                        const nUnits = (p.units || []).length;
                        // SC bar: 18 is standard victory condition
                        const scPct = Math.min(100, Math.round((nCenters / 18) * 100));
                        return (
                            <div key={pwr} className="dash-power-card"
                                 style={{'--power-color': color, '--power-glow': glow}}>
                                <div className="dash-power-name">{pwr}</div>
                                <div className="dash-power-ctrl">
                                    {p.is_controlled
                                        ? <span>{p.controller}</span>
                                        : <span className="dash-uncontrolled">uncontrolled</span>}
                                </div>

                                {/* SC progress bar */}
                                <div className="dash-sc-bar">
                                    <div className="dash-sc-fill" style={{width: `${scPct}%`, background: color}} />
                                    <span className="dash-sc-label">{nCenters} SC</span>
                                </div>

                                <div className="dash-power-counts">
                                    <div className="dash-power-count">
                                        <span className="dash-count-num">{nUnits}</span>
                                        <span className="dash-count-label">units</span>
                                    </div>
                                    <div className="dash-power-count">
                                        <span className="dash-count-num">{nCenters}</span>
                                        <span className="dash-count-label">centers</span>
                                    </div>
                                </div>

                                <div className="dash-power-units">
                                    {(p.units || []).map((u, i) => <span key={i} className="dash-unit">{u}</span>)}
                                </div>

                                <div className="dash-power-flags">
                                    <span className={`dash-flag ${p.order_is_set ? 'on' : 'off'}`}>
                                        {p.order_is_set ? 'ORDERS' : 'NO ORD'}
                                    </span>
                                    <span className={`dash-flag ${!p.wait ? 'on' : 'off'}`}>
                                        {p.wait ? 'WAIT' : 'READY'}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    }
}

// ─── History Tab ─────────────────────────────────────────────

class HistoryPanel extends React.Component {
    constructor(props) {
        super(props);
        this.state = {phases: [], loading: false, error: null, expandedPhase: null};
    }

    componentDidMount() {
        if (this.props.gameId) this.refresh();
    }

    componentDidUpdate(prevProps) {
        if (prevProps.gameId !== this.props.gameId && this.props.gameId) {
            this.refresh();
        }
    }

    refresh() {
        if (!this.props.gameId) return;
        this.setState({loading: true, error: null});
        api.getHistory(this.props.gameId)
            .then(data => this.setState({phases: data.phases || [], loading: false}))
            .catch(e => this.setState({error: e.message, loading: false}));
    }

    togglePhase(phaseName) {
        this.setState(s => ({
            expandedPhase: s.expandedPhase === phaseName ? null : phaseName
        }));
    }

    render() {
        const {phases, loading, error, expandedPhase} = this.state;

        if (!this.props.gameId) {
            return <div className="dash-empty">Select a game from the Games tab first.</div>;
        }

        return (
            <div className="dash-section">
                <div className="dash-toolbar">
                    <span className="dash-toolbar-info">{this.props.gameId} &mdash; {phases.length} phase(s)</span>
                    <button className="dash-btn" onClick={() => this.refresh()}>Refresh</button>
                </div>
                {error && <div className="dash-error">{error}</div>}
                {loading && <div className="dash-loading"><div className="dash-spinner" />Loading...</div>}
                {!loading && phases.length === 0 && (
                    <div className="dash-empty">No history yet. The game has not been processed.</div>
                )}
                <div className="dash-history-list">
                    {phases.map((phase, idx) => {
                        const phaseName = phase.name || `Phase ${idx}`;
                        const isExpanded = expandedPhase === phaseName;
                        const orders = phase.orders || {};
                        const results = phase.results || {};
                        const state = phase.state || {};
                        const units = state.units || {};
                        const centers = state.centers || {};
                        return (
                            <div key={phaseName} className={`dash-hist-phase ${isExpanded ? 'expanded' : ''}`}>
                                <div className="dash-hist-header"
                                     onClick={() => this.togglePhase(phaseName)}>
                                    <span className="dash-hist-arrow">
                                        {isExpanded ? '\u25BC' : '\u25B6'}
                                    </span>
                                    <span className="dash-hist-name">{phaseName}</span>
                                    <span className="dash-hist-summary">
                                        {Object.keys(orders).length} powers
                                    </span>
                                </div>
                                {isExpanded && (
                                    <div className="dash-hist-body">
                                        {Object.keys(orders).sort().map(pwr => {
                                            const color = POWER_COLORS[pwr] || '#888';
                                            const pwrOrders = orders[pwr] || [];
                                            const pwrResults = results[pwr] || [];
                                            const pwrUnits = units[pwr] || [];
                                            const pwrCenters = centers[pwr] || [];
                                            return (
                                                <div key={pwr} className="dash-hist-power">
                                                    <div className="dash-hist-power-head" style={{color}}>
                                                        {pwr}
                                                        <span className="dash-hist-power-stats">
                                                            {pwrUnits.length}u / {pwrCenters.length}sc
                                                        </span>
                                                    </div>
                                                    {pwrOrders.map((order, oi) => {
                                                        const result = pwrResults[oi];
                                                        const ok = result !== undefined && (!result || result.length === 0);
                                                        return (
                                                            <div key={oi} className="dash-hist-order">
                                                                <span>{order}</span>
                                                                <span className={ok ? 'dash-result-ok' : 'dash-result-fail'}>
                                                                    {result !== undefined ? (ok ? 'OK' : result.join(',')) : ''}
                                                                </span>
                                                            </div>
                                                        );
                                                    })}
                                                    {pwrOrders.length === 0 && (
                                                        <div className="dash-hist-no-orders">no orders</div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    }
}

// ─── Main Dashboard Component ────────────────────────────────

export class ContentDashboard extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            tab: 'games',
            selectedGameId: null,
        };
    }

    getPage() {
        return this.context;
    }

    selectGame(gameId) {
        this.setState({selectedGameId: gameId, tab: 'detail'});
    }

    render() {
        const page = this.getPage();
        const {tab, selectedGameId} = this.state;

        return (
            <div className="dash-root">
                <Helmet>
                    <title>Dashboard | Diplomacy</title>
                </Helmet>

                {/* Top bar */}
                <div className="dash-topbar">
                    <div className="dash-topbar-left">
                        <span className="dash-logo">DIPLOMACY</span>
                        <span className="dash-logo-sub">Command Center</span>
                    </div>
                    <div className="dash-topbar-right">
                        <span className="dash-user">
                            {page.channel ? page.channel.username : api.getUsername()}
                        </span>
                        <button className="dash-btn dash-btn-ghost" onClick={() => page.loadGames()}>
                            Exit Dashboard
                        </button>
                    </div>
                </div>

                {/* Tab bar */}
                <div className="dash-tabbar">
                    {[
                        ['games', 'GAMES'],
                        ['detail', 'DETAIL'],
                        ['history', 'HISTORY'],
                    ].map(([key, label]) => (
                        <button key={key}
                                className={`dash-tab ${tab === key ? 'active' : ''}`}
                                onClick={() => this.setState({tab: key})}>
                            {label}
                            {key !== 'games' && selectedGameId && (
                                <span className="dash-tab-game">{selectedGameId}</span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="dash-content">
                    {tab === 'games' && (
                        <GamesPanel onSelectGame={(id) => this.selectGame(id)}/>
                    )}
                    {tab === 'detail' && (
                        <GameDetailPanel
                            gameId={selectedGameId}
                            onBack={() => this.setState({tab: 'games'})}/>
                    )}
                    {tab === 'history' && (
                        <HistoryPanel gameId={selectedGameId}/>
                    )}
                </div>
            </div>
        );
    }

    componentDidMount() {
        window.scrollTo(0, 0);
        const page = this.getPage();
        if (page.channel && page.channel.token && !api.isLoggedIn()) {
            api.setToken(page.channel.token, page.channel.username);
        }
    }
}

ContentDashboard.contextType = PageContext;
