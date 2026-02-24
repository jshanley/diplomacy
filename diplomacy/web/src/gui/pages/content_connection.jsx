import React from 'react';
import {Connection} from "../../diplomacy/client/connection";
import {DipStorage} from "../utils/dipStorage";
import {Helmet} from "react-helmet";
import {PageContext} from "../components/page_context";

export class ContentConnection extends React.Component {
    constructor(props) {
        super(props);
        this.connection = null;

        const saved = DipStorage.getConnectionForm();
        this.state = {
            hostname: (saved && saved.hostname) || window.location.hostname,
            port: (saved && saved.port) || ((window.location.protocol.toLowerCase() === 'https:') ? 8433 : 8432),
            username: (saved && saved.username) || '',
            password: '',
            showServer: (saved && saved.showServerFields) || false,
            connecting: false,
        };
        this.onSubmit = this.onSubmit.bind(this);
    }

    onSubmit(e) {
        e.preventDefault();
        const page = this.context;
        const {hostname, port, username, password} = this.state;

        if (!username || !password) {
            return page.error('Enter a username and password.');
        }

        // Persist form data
        DipStorage.setConnectionHostname(hostname);
        DipStorage.setConnectionPort(port);
        DipStorage.setConnectionUsername(username);

        this.setState({connecting: true});
        page.info('Connecting...');

        if (this.connection) {
            this.connection.currentConnectionProcessing.stop();
        }

        this.connection = new Connection(hostname, port, window.location.protocol.toLowerCase() === 'https:');
        this.connection.onReconnectionError = page.onReconnectionError;

        this.connection.connect(page)
            .then(() => {
                page.connection = this.connection;
                this.connection = null;
                page.success(`Connected to ${hostname}:${port}`);
                page.connection.authenticate(username, password)
                    .then((channel) => {
                        page.channel = channel;
                        return channel.getAvailableMaps();
                    })
                    .then(availableMaps => {
                        for (let mapName of Object.keys(availableMaps))
                            availableMaps[mapName].powers.sort();
                        page.availableMaps = availableMaps;
                        const userGameIndices = DipStorage.getUserGames(page.channel.username);
                        if (userGameIndices && userGameIndices.length) {
                            return page.channel.getGamesInfo({games: userGameIndices});
                        }
                        return null;
                    })
                    .then((gamesInfo) => {
                        if (gamesInfo) {
                            page.updateMyGames(gamesInfo);
                        }
                        page.loadGames({success: `Signed in as ${username}`});
                    })
                    .catch((error) => {
                        this.setState({connecting: false});
                        page.error('Authentication failed: ' + error);
                    });
            })
            .catch((error) => {
                this.setState({connecting: false});
                page.error('Connection failed: ' + error);
            });
    }

    render() {
        const {hostname, port, username, password, showServer, connecting} = this.state;

        return (
            <div className="login-root">
                <Helmet>
                    <title>Sign In | Diplomacy</title>
                </Helmet>

                {/* Background grid effect */}
                <div className="login-bg">
                    <div className="login-grid" />
                </div>

                <div className="login-container">
                    {/* Logo / branding */}
                    <div className="login-brand">
                        <div className="login-title">DIPLOMACY</div>
                        <div className="login-subtitle">Command Center</div>
                    </div>

                    {/* Login card */}
                    <div className="login-card">
                        <form onSubmit={this.onSubmit}>
                            <div className="login-field">
                                <label className="login-label" htmlFor="username">USERNAME</label>
                                <input
                                    className="login-input"
                                    type="text"
                                    id="username"
                                    value={username}
                                    onChange={e => this.setState({username: e.target.value})}
                                    autoFocus
                                    autoComplete="username"
                                    placeholder="Enter username"
                                />
                            </div>

                            <div className="login-field">
                                <label className="login-label" htmlFor="password">PASSWORD</label>
                                <input
                                    className="login-input"
                                    type="password"
                                    id="password"
                                    value={password}
                                    onChange={e => this.setState({password: e.target.value})}
                                    autoComplete="current-password"
                                    placeholder="Enter password"
                                />
                            </div>

                            {/* Server settings toggle */}
                            <div className="login-server-toggle"
                                 onClick={() => this.setState({showServer: !showServer})}>
                                <span className="login-server-arrow">{showServer ? '\u25BC' : '\u25B6'}</span>
                                Server Settings
                            </div>

                            {showServer && (
                                <div className="login-server-fields">
                                    <div className="login-field login-field-inline">
                                        <label className="login-label" htmlFor="hostname">HOST</label>
                                        <input
                                            className="login-input"
                                            type="text"
                                            id="hostname"
                                            value={hostname}
                                            onChange={e => this.setState({hostname: e.target.value})}
                                        />
                                    </div>
                                    <div className="login-field login-field-inline">
                                        <label className="login-label" htmlFor="port">PORT</label>
                                        <input
                                            className="login-input"
                                            type="number"
                                            id="port"
                                            value={port}
                                            onChange={e => this.setState({port: parseInt(e.target.value) || 8432})}
                                        />
                                    </div>
                                </div>
                            )}

                            <button className="login-submit" type="submit" disabled={connecting}>
                                {connecting ? (
                                    <span className="login-submit-loading">
                                        <span className="login-spinner" />
                                        Connecting...
                                    </span>
                                ) : 'Sign In'}
                            </button>
                        </form>

                        <div className="login-hint">
                            New accounts are created automatically on first sign-in.
                        </div>
                    </div>

                    <div className="login-footer">
                        Diplomacy AI Platform
                    </div>
                </div>
            </div>
        );
    }

    componentDidMount() {
        window.scrollTo(0, 0);
    }
}

ContentConnection.contextType = PageContext;
