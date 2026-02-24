import React from 'react';
import { Helmet } from 'react-helmet';
import { PageContext } from '../components/page_context';
import { api } from '../utils/api';

export class ContentLanding extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            mode: 'join', // 'join' or 'create'
            code: '',
            displayName: api.getDisplayName() || '',
            mapName: 'standard',
            error: null,
            loading: false,
        };
        this.onJoin = this.onJoin.bind(this);
        this.onCreate = this.onCreate.bind(this);
        this.onCodeInput = this.onCodeInput.bind(this);
    }

    onCodeInput(e) {
        const val = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4);
        this.setState({ code: val });
    }

    /**
     * Ensure we have a stable identity token before making lobby calls.
     * If we already have one and the display name matches, reuse it.
     * Otherwise, create/refresh the identity.
     */
    async ensureIdentity(displayName) {
        const currentName = api.getDisplayName();
        if (api.isLoggedIn() && currentName && currentName.toLowerCase() === displayName.toLowerCase()) {
            return; // already have a matching identity
        }
        await api.identity(displayName);
    }

    async onJoin(e) {
        e.preventDefault();
        const { code, displayName } = this.state;
        if (!code || code.length !== 4) return this.setState({ error: 'Enter a 4-character game code' });
        if (!displayName.trim()) return this.setState({ error: 'Enter your name' });

        this.setState({ loading: true, error: null });
        try {
            await this.ensureIdentity(displayName.trim());
            const data = await api.lobbyJoin(code, displayName.trim());
            const page = this.context;
            page.loadLobby(data.code, data.player, data.lobby);
        } catch (err) {
            this.setState({ error: err.message, loading: false });
        }
    }

    async onCreate(e) {
        e.preventDefault();
        const { displayName, mapName } = this.state;
        if (!displayName.trim()) return this.setState({ error: 'Enter your name' });

        this.setState({ loading: true, error: null });
        try {
            await this.ensureIdentity(displayName.trim());
            const data = await api.lobbyCreate(displayName.trim(), mapName);
            const page = this.context;
            page.loadLobby(data.code, data.player, data.lobby);
        } catch (err) {
            this.setState({ error: err.message, loading: false });
        }
    }

    render() {
        const { mode, code, displayName, mapName, error, loading } = this.state;

        return (
            <div className="landing-root">
                <Helmet><title>Diplomacy</title></Helmet>
                <div className="landing-bg"><div className="landing-grid" /></div>

                <div className="landing-container">
                    <div className="landing-brand">
                        <div className="landing-title">DIPLOMACY</div>

                    </div>

                    <div className="landing-card">
                        <div className="landing-tabs">
                            <button
                                className={`landing-tab ${mode === 'join' ? 'active' : ''}`}
                                onClick={() => this.setState({ mode: 'join', error: null })}
                            >JOIN GAME</button>
                            <button
                                className={`landing-tab ${mode === 'create' ? 'active' : ''}`}
                                onClick={() => this.setState({ mode: 'create', error: null })}
                            >CREATE GAME</button>
                        </div>

                        {error && <div className="landing-error">{error}</div>}

                        {mode === 'join' ? (
                            <form onSubmit={this.onJoin}>
                                <div className="landing-code-group">
                                    <label className="landing-label">GAME CODE</label>
                                    <input
                                        className="landing-code-input"
                                        type="text"
                                        value={code}
                                        onChange={this.onCodeInput}
                                        placeholder="XKQR"
                                        maxLength={4}
                                        autoFocus
                                        autoComplete="off"
                                        spellCheck={false}
                                    />
                                </div>
                                <div className="landing-field">
                                    <label className="landing-label">YOUR NAME</label>
                                    <input
                                        className="landing-input"
                                        type="text"
                                        value={displayName}
                                        onChange={e => this.setState({ displayName: e.target.value })}
                                        placeholder="Enter your name"
                                        maxLength={20}
                                    />
                                </div>
                                <button className="landing-btn" type="submit" disabled={loading}>
                                    {loading ? 'JOINING...' : 'JOIN'}
                                </button>
                            </form>
                        ) : (
                            <form onSubmit={this.onCreate}>
                                <div className="landing-field">
                                    <label className="landing-label">YOUR NAME</label>
                                    <input
                                        className="landing-input"
                                        type="text"
                                        value={displayName}
                                        onChange={e => this.setState({ displayName: e.target.value })}
                                        placeholder="Enter your name"
                                        maxLength={20}
                                        autoFocus
                                    />
                                </div>
                                <div className="landing-field">
                                    <label className="landing-label">MAP</label>
                                    <select
                                        className="landing-select"
                                        value={mapName}
                                        onChange={e => this.setState({ mapName: e.target.value })}
                                    >
                                        <option value="standard">Standard (7 powers)</option>
                                        <option value="ancmed">Ancient Mediterranean</option>
                                        <option value="modern">Modern</option>
                                        <option value="pure">Pure</option>
                                    </select>
                                </div>
                                <button className="landing-btn" type="submit" disabled={loading}>
                                    {loading ? 'CREATING...' : 'CREATE GAME'}
                                </button>
                            </form>
                        )}
                    </div>
                </div>
            </div>
        );
    }
}

ContentLanding.contextType = PageContext;
