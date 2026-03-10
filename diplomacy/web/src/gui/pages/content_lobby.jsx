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
            // Talk phase state
            talkRound: 0,
            talkRoundState: '',
            talkNumRounds: 2,
            talkMaxMessages: 5,
            talkReadyPowers: [],
            messages: [],
            draftRecipient: '',
            draftMessage: '',
            sendingMessage: false,
            messagesSentThisRound: 0,
            readySent: false,
            messageFilter: 'all',   // 'all', 'sent', 'received'
            // Bot UI state
            showBotForm: false,
            botCount: 6,
            botApiKey: '',
            botModel: '',
            botProvider: 'anthropic',
            addingBots: false,
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
        this.onSendMessage = this.onSendMessage.bind(this);
        this.onReady = this.onReady.bind(this);
        this.onAddBots = this.onAddBots.bind(this);
        this.onDone = this.onDone.bind(this);
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
            if (!gs) return;
            this.setState(prev => {
                const newState = {
                    gameState: gs,
                    ordersData: ord,
                    talkRound: gs.talk_round || 0,
                    talkRoundState: gs.talk_round_state || '',
                    talkNumRounds: gs.talk_num_rounds || 2,
                    talkMaxMessages: gs.talk_max_messages || 5,
                    talkReadyPowers: gs.talk_ready_powers || [],
                    messages: gs.messages || [],
                };
                // Reset order state if phase changed
                if (prev.gameState && prev.gameState.phase !== gs.phase) {
                    newState.builtOrders = {};
                    newState.submitted = false;
                    newState.orderBuildingType = null;
                    newState.orderBuildingPath = [];
                    newState.readySent = false;
                }
                // Reset readySent and message counter if talk round changed
                if (prev.talkRound !== newState.talkRound ||
                    prev.talkRoundState !== newState.talkRoundState) {
                    newState.readySent = false;
                    newState.messagesSentThisRound = 0;
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

    async onDone() {
        // Auto-fill Hold for any unordered units, submit, and signal ready
        const { ordersData, builtOrders, gameState } = this.state;
        const yourPower = gameState.your_power;
        const units = (ordersData && ordersData.units) || [];
        const finalOrders = { ...builtOrders };
        // Only auto-fill Hold during Movement (or Talk orders_open which acts as Movement).
        // During Retreat/Adjustment, unordered units are left to the server default.
        // Guard: onDone should never fire during Talk round_open (negotiation).
        const phaseType = gameState.phase_type;
        if (phaseType === 'T' && this.state.talkRoundState !== 'orders_open') {
            return;
        }
        const isMovement = phaseType === 'M' || (phaseType === 'T' && this.state.talkRoundState === 'orders_open');
        if (isMovement) {
            for (const unit of units) {
                const loc = unit.substring(2, 5);
                if (!finalOrders[loc]) {
                    finalOrders[loc] = unit + ' H';
                }
            }
        }
        const orderList = Object.values(finalOrders).filter(Boolean);
        this.setState({ submitting: true, error: null });
        try {
            await api.lobbySubmitOrders(this.state.lobby.code, orderList, false);
            this.setState({ submitting: false, submitted: true, builtOrders: finalOrders });
            await api.lobbyReady(this.state.lobby.code);
            this.setState({ readySent: true });
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

    async onSendMessage(e) {
        e.preventDefault();
        const { draftRecipient, draftMessage } = this.state;
        if (!draftRecipient || !draftMessage.trim()) return;

        this.setState({ sendingMessage: true });
        try {
            await api.lobbySendMessage(
                this.state.lobby.code, draftRecipient, draftMessage.trim()
            );
            this.setState(prev => ({
                sendingMessage: false,
                draftMessage: '',
                messagesSentThisRound: prev.messagesSentThisRound + 1,
            }));
        } catch (err) {
            this.showError(err);
            this.setState({ sendingMessage: false });
        }
    }

    async onReady() {
        this.setState({ readySent: true });
        try {
            await api.lobbyReady(this.state.lobby.code);
        } catch (err) {
            this.showError(err);
            this.setState({ readySent: false });
        }
    }

    async onAddBots(e) {
        e.preventDefault();
        const { botCount, botApiKey, botModel, botProvider } = this.state;
        if (!botApiKey.trim()) return this.showError('Enter an API key');

        this.setState({ addingBots: true });
        try {
            const data = await api.lobbyAddBots(
                this.state.lobby.code, botCount,
                botApiKey.trim(), botModel.trim() || null, botProvider
            );
            this.setState({ addingBots: false, showBotForm: false, lobby: data.lobby });
        } catch (err) {
            this.showError(err);
            this.setState({ addingBots: false });
        }
    }

    renderWaiting() {
        const { lobby, player, error, starting, copied,
                showBotForm, botCount, botApiKey, botModel, botProvider, addingBots } = this.state;
        const isHost = player.is_host;
        const spotsLeft = lobby.n_powers - lobby.player_count;

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
                        {lobby.enable_talk && (
                            <span className="lobby-talk-badge">TALK {lobby.talk_rounds}R</span>
                        )}
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
                                {p.is_bot && <span className="lobby-bot-badge">AI</span>}
                                {p.username === player.username && <span className="lobby-you-badge">YOU</span>}
                            </span>
                        </div>
                    ))}
                    {Array.from({ length: spotsLeft }, (_, i) => (
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

                {isHost && spotsLeft > 0 && !showBotForm && (
                    <button
                        className="lobby-add-bot-btn"
                        onClick={() => this.setState({ showBotForm: true, botCount: Math.min(6, spotsLeft) })}
                    >+ ADD AI PLAYERS</button>
                )}

                {isHost && showBotForm && (
                    <form className="bot-form" onSubmit={this.onAddBots}>
                        <div className="bot-form-title">ADD AI PLAYERS</div>
                        <div className="landing-field">
                            <label className="landing-label">COUNT</label>
                            <select
                                className="landing-select"
                                value={botCount}
                                onChange={e => this.setState({ botCount: parseInt(e.target.value) })}
                            >
                                {Array.from({ length: spotsLeft }, (_, i) => (
                                    <option key={i + 1} value={i + 1}>{i + 1}</option>
                                ))}
                            </select>
                        </div>
                        <div className="landing-field">
                            <label className="landing-label">PROVIDER</label>
                            <select
                                className="landing-select"
                                value={botProvider}
                                onChange={e => this.setState({ botProvider: e.target.value })}
                            >
                                <option value="anthropic">Anthropic (Claude)</option>
                                <option value="openai">OpenAI</option>
                                <option value="google">Google (Gemini)</option>
                            </select>
                        </div>
                        <div className="landing-field">
                            <label className="landing-label">API KEY</label>
                            <input
                                className="landing-input"
                                type="password"
                                value={botApiKey}
                                onChange={e => this.setState({ botApiKey: e.target.value })}
                                placeholder="sk-..."
                            />
                        </div>
                        <div className="landing-field">
                            <label className="landing-label">MODEL (optional)</label>
                            <input
                                className="landing-input"
                                type="text"
                                value={botModel}
                                onChange={e => this.setState({ botModel: e.target.value })}
                                placeholder="Default model"
                            />
                        </div>
                        <div className="bot-form-actions">
                            <button
                                type="button"
                                className="order-action-btn order-clear-btn"
                                onClick={() => this.setState({ showBotForm: false })}
                            >CANCEL</button>
                            <button
                                type="submit"
                                className="order-action-btn order-submit-btn"
                                disabled={addingBots}
                            >{addingBots ? 'ADDING...' : 'ADD'}</button>
                        </div>
                    </form>
                )}

                {isHost && (
                    <button className="landing-btn" onClick={this.onStart} disabled={starting || lobby.player_count < 2}>
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

    renderTalkPanel() {
        const { gameState, player, talkRound, talkRoundState, talkNumRounds,
                talkMaxMessages, talkReadyPowers, messages, messageFilter,
                draftRecipient, draftMessage, sendingMessage, readySent } = this.state;
        if (!gameState) return null;

        const yourPower = gameState.your_power;
        const allPowers = Object.keys(gameState.powers);
        const otherPowers = allPowers.filter(p => p !== yourPower);
        const isRoundOpen = talkRoundState === 'round_open';

        // Use local counter (server holds messages until round closes)
        const sentThisRound = this.state.messagesSentThisRound;
        const canSend = isRoundOpen && sentThisRound < talkMaxMessages && !readySent;

        // Filter messages
        const filteredMessages = messages.filter(m => {
            if (messageFilter === 'sent') return m.sender === yourPower;
            if (messageFilter === 'received') return m.sender !== yourPower;
            return true;
        });

        return (
            <div className="game-section talk-panel">
                <div className="talk-header">
                    <span className="talk-round-label">
                        TALK ROUND {talkRound}/{talkNumRounds}
                    </span>
                    <span className={`talk-state-label ${talkRoundState}`}>
                        {isRoundOpen ? 'OPEN' : talkRoundState === 'orders_open' ? 'ORDERS' : talkRoundState.toUpperCase()}
                    </span>
                </div>

                {/* Ready status dots */}
                <div className="talk-ready-row">
                    {allPowers.map(p => (
                        <span
                            key={p}
                            className={`talk-ready-dot ${talkReadyPowers.includes(p) ? 'ready' : ''} ${p === yourPower ? 'is-you' : ''}`}
                            title={p}
                        >{p.substring(0, 3)}</span>
                    ))}
                </div>

                {/* Message filter toggle */}
                <div className="talk-filter-row">
                    {['all', 'sent', 'received'].map(f => (
                        <button key={f}
                                className={`talk-filter-btn ${messageFilter === f ? 'active' : ''}`}
                                onClick={() => this.setState({ messageFilter: f })}>
                            {f.toUpperCase()}
                        </button>
                    ))}
                </div>

                {/* Messages thread */}
                <div className="talk-messages">
                    {filteredMessages.length === 0 && (
                        <div className="talk-no-messages">
                            {isRoundOpen && messages.length === 0
                                ? 'Messages are revealed when all players are ready.'
                                : filteredMessages.length === 0 && messages.length > 0
                                    ? `No ${messageFilter} messages.`
                                    : 'No messages this phase.'}
                        </div>
                    )}
                    {filteredMessages.map((m, i) => (
                        <div key={i} className={`talk-msg ${m.sender === yourPower ? 'sent' : 'received'}`}>
                            <div className="talk-msg-header">
                                <span className="talk-msg-sender">{m.sender}</span>
                                <span className="talk-msg-arrow">{m.recipient === 'GLOBAL' ? 'PUBLIC' : `to ${m.recipient}`}</span>
                            </div>
                            <div className="talk-msg-body">{m.message}</div>
                        </div>
                    ))}
                </div>

                {/* Compose area (only during round_open) */}
                {isRoundOpen && !readySent && (
                    <form className="talk-compose" onSubmit={this.onSendMessage}>
                        <div className="talk-compose-top">
                            <select
                                className="talk-recipient-select"
                                value={draftRecipient}
                                onChange={e => this.setState({ draftRecipient: e.target.value })}
                            >
                                <option value="">To...</option>
                                {otherPowers.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                ))}
                                <option value="GLOBAL">PUBLIC (all)</option>
                            </select>
                            <span className="talk-msg-counter">{sentThisRound}/{talkMaxMessages}</span>
                        </div>
                        <textarea
                            className="talk-textarea"
                            value={draftMessage}
                            onChange={e => this.setState({ draftMessage: e.target.value })}
                            placeholder="Write a message..."
                            maxLength={500}
                            rows={2}
                        />
                        <button
                            type="submit"
                            className="talk-send-btn"
                            disabled={sendingMessage || !canSend || !draftRecipient || !draftMessage.trim()}
                        >{sendingMessage ? 'SENDING...' : 'SEND'}</button>
                    </form>
                )}

                {/* Done talking button */}
                {isRoundOpen && (
                    <button
                        className={`talk-ready-btn ${readySent ? 'sent' : ''}`}
                        onClick={this.onReady}
                        disabled={readySent}
                    >{readySent ? 'WAITING FOR OTHERS...' : 'DONE TALKING'}</button>
                )}
            </div>
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
                // During orders_open in a Talk phase, orders are Movement orders
                const effectivePhaseType = (phaseType === 'T') ? 'M' : phaseType;

                // Compute allowed order types for the current power
                if (gameEngine.orderableLocations && !isDone) {
                    const orderTypeToLocs = gameEngine.getOrderTypeToLocs(yourPower);
                    allowedOrderTypes = Object.keys(orderTypeToLocs);
                    if (allowedOrderTypes.length && effectivePhaseType) {
                        POSSIBLE_ORDERS.sortOrderTypes(allowedOrderTypes, effectivePhaseType);
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
                    {/* Talk phase panel */}
                    {!isDone && gameState.phase_type === 'T' && this.state.talkRoundState === 'round_open' && (
                        this.renderTalkPanel()
                    )}

                    {/* Delivered messages — shown during orders_open after Talk rounds */}
                    {!isDone && gameState.phase_type === 'T' && this.state.talkRoundState === 'orders_open'
                        && this.state.messages && this.state.messages.length > 0 && (() => {
                        const mf = this.state.messageFilter;
                        const filtered = this.state.messages.filter(msg => {
                            if (mf === 'sent') return msg.sender === yourPower;
                            if (mf === 'received') return msg.sender !== yourPower;
                            return true;
                        });
                        return (
                            <div className="game-section">
                                <div className="game-section-title">MESSAGES</div>
                                <div className="talk-filter-row">
                                    {['all', 'sent', 'received'].map(f => (
                                        <button key={f}
                                                className={`talk-filter-btn ${mf === f ? 'active' : ''}`}
                                                onClick={() => this.setState({ messageFilter: f })}>
                                            {f.toUpperCase()}
                                        </button>
                                    ))}
                                </div>
                                <div className="talk-messages">
                                    {filtered.map((msg, i) => (
                                        <div key={i} className={`talk-msg ${msg.sender === yourPower ? 'sent' : 'received'}`}>
                                            <div className="talk-msg-header">
                                                <strong>{msg.sender}</strong>
                                                {msg.recipient !== 'GLOBAL' ? ` → ${msg.recipient}` : ' (GLOBAL)'}
                                            </div>
                                            <div className="talk-msg-body">{msg.message}</div>
                                        </div>
                                    ))}
                                    {filtered.length === 0 && (
                                        <div className="talk-no-messages">No {mf} messages.</div>
                                    )}
                                </div>
                            </div>
                        );
                    })()}

                    {/* Order type selector — shown during orders_open (Talk) or M/R/A phases */}
                    {!isDone && allowedOrderTypes.length > 0 && !submitted
                        && (gameState.phase_type !== 'T' || this.state.talkRoundState === 'orders_open') && (
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
                    {!isDone && (gameState.phase_type !== 'T' || this.state.talkRoundState === 'orders_open') && (
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
                            {!submitted && (
                                <div className="order-actions">
                                    {orderedCount > 0 && (
                                        <button
                                            className="order-action-btn order-clear-btn"
                                            onClick={() => this.onClearOrders()}
                                        >CLEAR ALL</button>
                                    )}
                                    <button
                                        className="order-action-btn order-submit-btn"
                                        onClick={this.onDone}
                                        disabled={submitting}
                                    >{submitting ? 'SUBMITTING...' : (
                                        (phaseType === 'M' || phaseType === 'T')
                                            ? `DONE (${orderableCount - orderedCount} will hold)`
                                            : 'DONE'
                                    )}</button>
                                </div>
                            )}
                            {submitted && !this.state.readySent && (
                                <div className="talk-ready-btn sent" style={{textAlign: 'center', marginTop: 8}}>
                                    WAITING FOR OTHERS...
                                </div>
                            )}
                            {this.state.readySent && (
                                <div className="talk-ready-btn sent" style={{textAlign: 'center', marginTop: 8}}>
                                    WAITING FOR OTHERS...
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
                            {processing ? 'PROCESSING...' : (gameState.phase_type === 'T' ? 'FORCE ADVANCE' : 'PROCESS PHASE')}
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
