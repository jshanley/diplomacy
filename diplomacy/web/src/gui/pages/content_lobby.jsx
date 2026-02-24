import React from 'react';
import { Helmet } from 'react-helmet';
import { PageContext } from '../components/page_context';
import { api } from '../utils/api';
import { Game } from '../../diplomacy/engine/game';
import { MapData } from '../utils/map_data';
import { Order } from '../utils/order';
import { getMapComponent } from '../utils/map_components';
import { extendOrderBuilding, ORDER_BUILDER, POSSIBLE_ORDERS } from '../utils/order_building';
import { confirmAlert } from 'react-confirm-alert';
import { SelectLocationForm } from '../forms/select_location_form';
import { SelectViaForm } from '../forms/select_via_form';

/**
 * Generate agent instructions for connecting to a lobby.
 * Covers only: get identity, join, poll until started.
 * Points to /api/docs for the full API reference.
 */
function buildAgentInstructions(baseUrl, code) {
    return `# Join a Diplomacy Game

## 1. Get an identity

POST ${baseUrl}/api/auth/identity
Content-Type: application/json

{"display_name": "<your agent name>"}

Save the \`token\` from the response. Pass it as \`Authorization: Bearer <token>\` on all subsequent requests.

## 2. Join the lobby

POST ${baseUrl}/api/lobby/join
Authorization: Bearer <token>
Content-Type: application/json

{"code": "${code}", "display_name": "<your agent name>"}

## 3. Wait for the game to start

Poll until \`status\` is \`"started"\`:

GET ${baseUrl}/api/lobby/${code}

Once started, your game endpoints are under \`${baseUrl}/api/lobby/${code}/\`.

## Full API docs

GET ${baseUrl}/api/docs
`;
}

/**
 * Build a minimal Game instance from the lobby API game state response.
 * Also populates possibleOrders/orderableLocations/ordersTree if order data is available.
 */
function buildGameStub(gameState, ordersData) {
    const powerStates = {};
    for (const [name, p] of Object.entries(gameState.powers)) {
        powerStates[name] = {
            name,
            controller: { '0': p.controller || name },
            vote: null,
            order_is_set: p.order_is_set || 0,
            wait: p.wait || false,
            centers: p.centers || [],
            homes: p.homes || [],
            units: p.units || [],
            retreats: p.retreats || {},
            influence: p.influence || [],
            orders: {},
            adjust: [],
        };
    }

    const game = new Game({
        game_id: gameState.game_id,
        map_name: gameState.map_name,
        messages: {},
        role: gameState.your_power,
        rules: ['POWER_CHOICE'],
        status: gameState.status || 'active',
        timestamp_created: Date.now(),
        deadline: 0,
        message_history: {},
        order_history: {},
        state_history: {},
        result_history: {},
        n_controls: Object.keys(gameState.powers).length,
        registration_password: null,
        phase_abbr: gameState.phase,
        powers: powerStates,
        observer_level: null,
        controlled_powers: [gameState.your_power],
    });

    // Populate the orders tree for map-based order building
    if (ordersData && ordersData.all_possible_orders && ordersData.all_orderable_locations) {
        game.setPossibleOrders({
            possible_orders: ordersData.all_possible_orders,
            orderable_locations: ordersData.all_orderable_locations,
        });
    }

    return game;
}

export class ContentLobby extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            lobby: props.lobby,
            player: props.player,
            error: null,
            starting: false,
            copied: false,
            // Game state (after start)
            gameState: null,
            ordersData: null,       // raw orders API response
            // Map-based order building
            builtOrders: {},        // {loc: orderString} — orders built by clicking the map
            orderBuildingType: null, // current order type letter (H, M, S, C, etc.)
            orderBuildingPath: [],   // partial order path being built
            submitting: false,
            submitted: false,
            processing: false,
            showAbbreviations: true,
        };
        this.pollTimer = null;
        this.onStart = this.onStart.bind(this);
        this.onSubmitOrders = this.onSubmitOrders.bind(this);
        this.onProcess = this.onProcess.bind(this);
        this.onOrderBuilding = this.onOrderBuilding.bind(this);
        this.onOrderBuilt = this.onOrderBuilt.bind(this);
        this.onSelectLocation = this.onSelectLocation.bind(this);
        this.onSelectVia = this.onSelectVia.bind(this);
        this.onCopyAgentInstructions = this.onCopyAgentInstructions.bind(this);
    }

    componentDidMount() {
        this.pollTimer = setInterval(() => this.poll(), 2000);
    }

    componentWillUnmount() {
        if (this.pollTimer) clearInterval(this.pollTimer);
        if (this.errorTimer) clearTimeout(this.errorTimer);
    }

    onCopyAgentInstructions() {
        const { lobby } = this.state;
        const baseUrl = window.location.origin;
        const text = buildAgentInstructions(baseUrl, lobby.code);
        navigator.clipboard.writeText(text).then(() => {
            this.setState({ copied: true });
            setTimeout(() => this.setState({ copied: false }), 2000);
        }).catch(() => {
            // Fallback for non-HTTPS contexts
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            this.setState({ copied: true });
            setTimeout(() => this.setState({ copied: false }), 2000);
        });
    }

    showError(msg) {
        if (this.errorTimer) clearTimeout(this.errorTimer);
        const text = (msg && typeof msg === 'object' && msg.message) ? msg.message : String(msg);
        this.setState({ error: text });
        this.errorTimer = setTimeout(() => this.setState({ error: null }), 3000);
    }

    async poll() {
        const { lobby } = this.state;
        if (lobby.status !== 'started') {
            try {
                const data = await api.lobbyState(lobby.code);
                this.setState({ lobby: data.lobby });
                if (data.lobby.status === 'started') {
                    const me = data.lobby.players.find(
                        p => p.username === this.state.player.username
                    );
                    if (me) {
                        this.setState(prev => ({
                            player: { ...prev.player, power: me.power }
                        }), () => this.fetchGameState());
                    }
                }
            } catch (err) { /* ignore */ }
        } else {
            await this.fetchGameState();
        }
    }

    async fetchGameState() {
        try {
            const [gs, ord] = await Promise.all([
                api.lobbyGameState(this.state.lobby.code),
                api.lobbyGetOrders(this.state.lobby.code),
            ]);
            this.setState(prev => {
                const newState = { gameState: gs, ordersData: ord };
                // Reset order state if phase changed
                if (prev.gameState && prev.gameState.phase !== gs.phase) {
                    newState.builtOrders = {};
                    newState.submitted = false;
                    newState.orderBuildingType = null;
                    newState.orderBuildingPath = [];
                }
                return newState;
            });
        } catch (err) { /* ignore */ }
    }

    async onStart() {
        this.setState({ starting: true, error: null });
        try {
            const data = await api.lobbyStart(this.state.lobby.code);
            const me = data.lobby.players.find(
                p => p.username === this.state.player.username
            );
            this.setState({
                lobby: data.lobby,
                starting: false,
                player: me ? { ...this.state.player, power: me.power } : this.state.player,
            }, () => this.fetchGameState());
        } catch (err) {
            this.showError(err);
            this.setState({ starting: false });
        }
    }

    // --- Order building callbacks ---

    onOrderBuilding(powerName, path) {
        // path includes the type as first element, strip it for storage
        this.setState({ orderBuildingPath: path.slice(1) });
    }

    onOrderBuilt(powerName, orderString) {
        const order = new Order(orderString, true);
        this.setState(prev => ({
            builtOrders: { ...prev.builtOrders, [order.loc]: orderString },
            orderBuildingPath: [],
        }));
    }

    onSelectLocation(possibleLocations, powerName, orderType, orderPath) {
        confirmAlert({
            customUI: ({ onClose }) => (
                <SelectLocationForm
                    path={orderPath}
                    locations={possibleLocations}
                    onSelect={(location) => {
                        extendOrderBuilding(
                            powerName, orderType, orderPath, location,
                            this.onOrderBuilding, this.onOrderBuilt,
                            (msg) => this.showError(msg)
                        );
                        onClose();
                    }}
                    onClose={() => {
                        this.setState({ orderBuildingPath: [] });
                        onClose();
                    }}
                />
            )
        });
    }

    onSelectVia(location, powerName, orderPath) {
        confirmAlert({
            customUI: ({ onClose }) => (
                <SelectViaForm
                    path={orderPath}
                    onSelect={(moveType) => {
                        setTimeout(() => {
                            if (moveType && ['M', 'V'].includes(moveType)) {
                                extendOrderBuilding(
                                    powerName, moveType, orderPath, location,
                                    this.onOrderBuilding, this.onOrderBuilt,
                                    (msg) => this.showError(msg)
                                );
                            }
                            onClose();
                        }, 0);
                    }}
                    onClose={() => {
                        this.setState({ orderBuildingPath: [] });
                        onClose();
                    }}
                />
            )
        });
    }

    onRemoveOrder(loc) {
        this.setState(prev => {
            const orders = { ...prev.builtOrders };
            delete orders[loc];
            return { builtOrders: orders };
        });
    }

    onClearOrders() {
        this.setState({ builtOrders: {}, orderBuildingPath: [], orderBuildingType: null });
    }

    async onSubmitOrders() {
        const orderList = Object.values(this.state.builtOrders).filter(Boolean);
        this.setState({ submitting: true, error: null });
        try {
            await api.lobbySubmitOrders(this.state.lobby.code, orderList, false);
            this.setState({ submitting: false, submitted: true });
        } catch (err) {
            this.showError(err);
            this.setState({ submitting: false });
        }
    }

    async onProcess() {
        this.setState({ processing: true, error: null });
        try {
            await api.lobbyProcess(this.state.lobby.code);
            this.setState({
                processing: false, builtOrders: {}, submitted: false,
                orderBuildingType: null, orderBuildingPath: [],
            });
            await this.fetchGameState();
        } catch (err) {
            this.showError(err);
            this.setState({ processing: false });
        }
    }

    renderWaiting() {
        const { lobby, player, error, starting, copied } = this.state;
        const isHost = player.is_host;

        return (
            <div className="lobby-container">
                <div className="lobby-header">
                    <div className="lobby-code-display">
                        <div className="lobby-code-label">GAME CODE</div>
                        <div className="lobby-code">{lobby.code}</div>
                    </div>
                    <div className="lobby-meta">
                        <span className="lobby-map">{lobby.map_name}</span>
                        <span className="lobby-count">{lobby.player_count} / {lobby.n_powers} players</span>
                    </div>
                </div>

                {error && <div className="landing-error">{error}</div>}

                <div className="lobby-players">
                    <div className="lobby-players-title">PLAYERS</div>
                    {lobby.players.map(p => (
                        <div key={p.username} className={`lobby-player ${p.username === player.username ? 'is-you' : ''}`}>
                            <span className="lobby-player-name">
                                {p.display_name}
                                {p.is_host && <span className="lobby-host-badge">HOST</span>}
                                {p.username === player.username && <span className="lobby-you-badge">YOU</span>}
                            </span>
                        </div>
                    ))}
                    {Array.from({ length: lobby.n_powers - lobby.player_count }, (_, i) => (
                        <div key={`empty-${i}`} className="lobby-player empty">
                            <span className="lobby-player-name">Waiting for player...</span>
                        </div>
                    ))}
                </div>

                <button
                    className={`lobby-copy-api-btn ${copied ? 'copied' : ''}`}
                    onClick={this.onCopyAgentInstructions}
                >
                    {copied ? 'COPIED' : 'COPY API'}
                </button>

                {isHost && (
                    <button className="landing-btn" onClick={this.onStart} disabled={starting}>
                        {starting ? 'STARTING...' : `START GAME (${lobby.player_count} player${lobby.player_count !== 1 ? 's' : ''})`}
                    </button>
                )}

                {!isHost && (
                    <div className="lobby-waiting">Waiting for host to start the game...</div>
                )}
            </div>
        );
    }

    renderMap(gameEngine, mapInfo, orderBuilding, mapOrders) {
        const MapComponent = getMapComponent(gameEngine.map_name);
        const mapData = new MapData(mapInfo, gameEngine);
        return (
            <MapComponent
                game={gameEngine}
                mapData={mapData}
                showAbbreviations={this.state.showAbbreviations}
                onError={(msg) => this.showError(msg)}
                orderBuilding={orderBuilding}
                onOrderBuilding={this.onOrderBuilding}
                onOrderBuilt={this.onOrderBuilt}
                onSelectLocation={this.onSelectLocation}
                onSelectVia={this.onSelectVia}
                orders={mapOrders}
            />
        );
    }

    renderGame() {
        const { lobby, player, error, gameState, ordersData,
                builtOrders, orderBuildingType, orderBuildingPath,
                submitting, submitted, processing } = this.state;
        const isHost = player.is_host;

        if (!gameState) {
            return (
                <div className="lobby-container">
                    <div className="lobby-waiting">Loading game state...</div>
                </div>
            );
        }

        const phase = gameState.phase;
        const isDone = gameState.is_done;
        const yourPower = gameState.your_power;

        // Build standings
        const standings = Object.entries(gameState.powers)
            .map(([name, p]) => ({ name, units: p.units.length, centers: p.centers.length, isYou: p.is_you }))
            .sort((a, b) => b.centers - a.centers);

        // Build Game stub for SVG rendering
        let gameEngine = null;
        let mapInfo = null;
        let orderBuilding = null;
        let phaseType = null;
        let allowedOrderTypes = [];
        let activeOrderType = null;

        try {
            if (gameState.map_info) {
                mapInfo = gameState.map_info;
                gameEngine = buildGameStub(gameState, ordersData);
                phaseType = gameEngine.getPhaseType();

                // Compute allowed order types for the current power
                if (gameEngine.orderableLocations && !isDone) {
                    const orderTypeToLocs = gameEngine.getOrderTypeToLocs(yourPower);
                    allowedOrderTypes = Object.keys(orderTypeToLocs);
                    if (allowedOrderTypes.length && phaseType) {
                        POSSIBLE_ORDERS.sortOrderTypes(allowedOrderTypes, phaseType);
                        if (orderBuildingType && allowedOrderTypes.includes(orderBuildingType)) {
                            activeOrderType = orderBuildingType;
                        } else {
                            activeOrderType = allowedOrderTypes[0];
                        }
                    }
                }

                // Build the orderBuilding prop for the map
                if (activeOrderType && !submitted) {
                    orderBuilding = {
                        type: activeOrderType,
                        path: orderBuildingPath,
                        power: yourPower,
                        builder: ORDER_BUILDER[activeOrderType],
                    };
                }
            }
        } catch (e) {
            console.error('Failed to build game stub for map rendering:', e);
        }

        // Convert builtOrders to the format the map expects: {powerName: [orderStrings]}
        const mapOrders = {};
        if (Object.keys(builtOrders).length > 0) {
            mapOrders[yourPower] = Object.values(builtOrders);
        }

        // Count how many locations need orders
        const orderableCount = ordersData ? (ordersData.orderable_locations || []).length : 0;
        const orderedCount = Object.keys(builtOrders).length;

        return (
            <div className="lobby-container game-active">
                <div className="game-header">
                    <div className="game-phase">{phase}</div>
                    <div className="game-your-power">
                        <span className="game-power-label">You are</span>
                        <span className="game-power-name">{yourPower}</span>
                    </div>
                    <div className="game-code-small">{lobby.code}</div>
                </div>

                {error && (
                    <div className="game-toast" onClick={() => this.setState({ error: null })}>
                        {error}
                    </div>
                )}

                {isDone && (
                    <div className="game-done">
                        <div className="game-done-title">GAME OVER</div>
                    </div>
                )}

                {/* Map */}
                {gameEngine && mapInfo && (
                    <div className="game-map-container">
                        {this.renderMap(gameEngine, mapInfo, orderBuilding, mapOrders)}
                    </div>
                )}

                <div className="game-sidebar">
                    {/* Order type selector */}
                    {!isDone && allowedOrderTypes.length > 0 && !submitted && (
                        <div className="game-section">
                            <div className="game-section-title">ORDER TYPE</div>
                            <div className="order-type-buttons">
                                {allowedOrderTypes.map(t => (
                                    <button
                                        key={t}
                                        className={`order-type-btn ${activeOrderType === t ? 'active' : ''}`}
                                        onClick={() => this.setState({ orderBuildingType: t, orderBuildingPath: [] })}
                                    >
                                        {ORDER_BUILDER[t].name} ({t})
                                    </button>
                                ))}
                            </div>
                            {orderBuildingPath.length > 0 && (
                                <div className="order-building-status">
                                    Building: {activeOrderType} {orderBuildingPath.join(' ')} ...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Built orders list */}
                    {!isDone && (
                        <div className="game-section">
                            <div className="game-section-title">
                                {submitted ? 'ORDERS SUBMITTED' : `ORDERS (${orderedCount}/${orderableCount})`}
                            </div>
                            {orderedCount === 0 && !submitted && (
                                <div className="lobby-waiting" style={{animation: 'none', opacity: 0.6}}>
                                    Click units on the map to build orders
                                </div>
                            )}
                            {Object.entries(builtOrders).map(([loc, orderStr]) => (
                                <div key={loc} className="built-order">
                                    <span className="built-order-text">{orderStr}</span>
                                    {!submitted && (
                                        <button
                                            className="built-order-remove"
                                            onClick={() => this.onRemoveOrder(loc)}
                                            title="Remove order"
                                        >x</button>
                                    )}
                                </div>
                            ))}
                            {orderedCount > 0 && !submitted && (
                                <div className="order-actions">
                                    <button
                                        className="order-action-btn order-clear-btn"
                                        onClick={() => this.onClearOrders()}
                                    >CLEAR ALL</button>
                                    <button
                                        className="order-action-btn order-submit-btn"
                                        onClick={this.onSubmitOrders}
                                        disabled={submitting}
                                    >{submitting ? 'SUBMITTING...' : 'SUBMIT ORDERS'}</button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Standings */}
                    <div className="game-section">
                        <div className="game-section-title">STANDINGS</div>
                        {standings.map(s => (
                            <div key={s.name} className={`game-standing ${s.isYou ? 'is-you' : ''}`}>
                                <span className="game-standing-name">{s.name}</span>
                                <span className="game-standing-stats">
                                    {s.centers} SC &middot; {s.units} units
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Host controls */}
                    {isHost && !isDone && (
                        <button
                            className="landing-btn game-process-btn"
                            onClick={this.onProcess}
                            disabled={processing}
                        >
                            {processing ? 'PROCESSING...' : 'PROCESS PHASE'}
                        </button>
                    )}
                </div>
            </div>
        );
    }

    render() {
        const { lobby } = this.state;
        const isStarted = lobby.status === 'started';

        return (
            <div className="lobby-root">
                <Helmet><title>{isStarted ? `Game ${lobby.code}` : `Lobby ${lobby.code}`} | Diplomacy</title></Helmet>
                <div className="landing-bg"><div className="landing-grid" /></div>
                {isStarted ? this.renderGame() : this.renderWaiting()}
            </div>
        );
    }
}

ContentLobby.contextType = PageContext;
