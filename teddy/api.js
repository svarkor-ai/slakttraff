/* Släktträff 2026 — API client. All backend calls in one place.
   Every call carries the session token; a 401 clears it and returns to the
   password screen (handled via onUnauthorized callback set by app.js). */
'use strict';

const TOKEN_KEY = 'slakttraff_token';

const API = {
    onUnauthorized: null,

    token() {
        return sessionStorage.getItem(TOKEN_KEY);
    },

    setToken(token) {
        if (token) {
            sessionStorage.setItem(TOKEN_KEY, token);
        } else {
            sessionStorage.removeItem(TOKEN_KEY);
        }
    },

    _headers() {
        const headers = { 'Content-Type': 'application/json' };
        const token = this.token();
        if (token) {
            headers['Authorization'] = 'Bearer ' + token;
        }
        return headers;
    },

    async _request(url, options) {
        const res = await fetch(url, options);
        if (res.status === 401 && this.onUnauthorized) {
            this.setToken(null);
            this.onUnauthorized();
            throw new Error('Sessionen har upphört — logga in igen.');
        }
        return res;
    },

    async login(password) {
        const res = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password }),
        });
        if (!res.ok) {
            return null;
        }
        const body = await res.json();
        this.setToken(body.token);
        return body.token;
    },

    async fetchPersons() {
        const res = await this._request('/api/persons/', { headers: this._headers() });
        if (!res.ok) {
            throw new Error('Kunde inte hämta släktträdet (HTTP ' + res.status + ')');
        }
        return res.json();
    },

    async submitRsvp(personId, status, contact) {
        const res = await this._request('/api/persons/' + personId + '/rsvp', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({
                status: status,
                email: contact.email,
                phone: contact.phone || null,
                notes: contact.notes || null,
            }),
        });
        if (!res.ok) {
            throw new Error('Kunde inte spara svaret (HTTP ' + res.status + ')');
        }
        return res.json();
    },

    async submitRegistration(payload) {
        const res = await this._request('/api/registrations/', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            throw new Error('Kunde inte skicka anmälan (HTTP ' + res.status + ')');
        }
        return res.json();
    },
};
