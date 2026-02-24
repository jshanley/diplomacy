// HTTP REST API helper.
// Uses fetch() against the same host that serves the web UI.

const STORAGE_KEY = 'diplomacy_identity';

function getBaseUrl() {
    return window.location.origin;
}

let _token = null;
let _username = null;
let _displayName = null;

// Restore identity from localStorage on load
function _restoreIdentity() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const { token, username, display_name } = JSON.parse(stored);
            if (token && username) {
                _token = token;
                _username = username;
                _displayName = display_name || username;
            }
        }
    } catch (e) { /* ignore */ }
}

function _persistIdentity() {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            token: _token,
            username: _username,
            display_name: _displayName,
        }));
    } catch (e) { /* ignore */ }
}

_restoreIdentity();

export const api = {
    getToken() {
        return _token;
    },

    getUsername() {
        return _username;
    },

    getDisplayName() {
        return _displayName;
    },

    isLoggedIn() {
        return !!_token;
    },

    setToken(token, username) {
        _token = token;
        _username = username;
        _persistIdentity();
    },

    /**
     * Get or create a stable identity from a display name.
     * No password required — Jackbox-style ephemeral identity.
     */
    async identity(displayName) {
        const resp = await fetch(`${getBaseUrl()}/api/auth/identity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: displayName }),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error);
        _token = data.token;
        _username = data.username;
        _displayName = data.display_name || displayName;
        _persistIdentity();
        return data;
    },

    async login(username, password) {
        const resp = await fetch(`${getBaseUrl()}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error);
        _token = data.token;
        _username = data.username;
        _persistIdentity();
        return data;
    },

    logout() {
        _token = null;
        _username = null;
        _displayName = null;
        try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
    },

    async _fetch(path, options = {}) {
        if (!_token) throw new Error('Not logged in');
        const headers = {
            'Authorization': `Bearer ${_token}`,
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        };
        const resp = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error);
        return data;
    },

    async listGames() {
        return this._fetch('/api/games');
    },

    async getGame(gameId) {
        return this._fetch(`/api/games/${encodeURIComponent(gameId)}`);
    },

    async getHistory(gameId) {
        return this._fetch(`/api/games/${encodeURIComponent(gameId)}/history`);
    },

    async createGame(params) {
        return this._fetch('/api/games', {
            method: 'POST',
            body: JSON.stringify(params),
        });
    },

    async deleteGame(gameId) {
        return this._fetch(`/api/games/${encodeURIComponent(gameId)}`, {
            method: 'DELETE',
        });
    },

    async processGame(gameId) {
        return this._fetch(`/api/games/${encodeURIComponent(gameId)}/process`, {
            method: 'POST',
        });
    },

    // --- Lobby API (Jackbox-style) ---

    async lobbyCreate(displayName, mapName = 'standard', assignment = 'random') {
        return this._fetch('/api/lobby/create', {
            method: 'POST',
            body: JSON.stringify({ display_name: displayName, map_name: mapName, assignment }),
        });
    },

    async lobbyJoin(code, displayName) {
        return this._fetch('/api/lobby/join', {
            method: 'POST',
            body: JSON.stringify({ code, display_name: displayName }),
        });
    },

    async lobbyState(code) {
        const resp = await fetch(`${getBaseUrl()}/api/lobby/${code}`, {
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error);
        return data;
    },

    async lobbyStart(code) {
        return this._fetch(`/api/lobby/${code}/start`, { method: 'POST' });
    },

    async lobbyGameState(code) {
        return this._fetch(`/api/lobby/${code}/game`);
    },

    async lobbyGetOrders(code) {
        return this._fetch(`/api/lobby/${code}/orders`);
    },

    async lobbySubmitOrders(code, orders, wait = false) {
        return this._fetch(`/api/lobby/${code}/orders`, {
            method: 'POST',
            body: JSON.stringify({ orders, wait }),
        });
    },

    async lobbyProcess(code) {
        return this._fetch(`/api/lobby/${code}/process`, { method: 'POST' });
    },
};
