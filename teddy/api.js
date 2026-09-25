/* Släktträff 2026 — API client. All backend calls in one place. */
'use strict';

const API = {
    async fetchPersons() {
        const res = await fetch('/api/persons/');
        if (!res.ok) {
            throw new Error('Kunde inte hämta släktträdet (HTTP ' + res.status + ')');
        }
        return res.json();
    },

    async submitRsvp(personId, status) {
        const res = await fetch('/api/persons/' + personId + '/rsvp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: status }),
        });
        if (!res.ok) {
            throw new Error('Kunde inte spara svaret (HTTP ' + res.status + ')');
        }
        return res.json();
    },

    async submitRegistration(payload) {
        const res = await fetch('/api/registrations/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            throw new Error('Kunde inte skicka anmälan (HTTP ' + res.status + ')');
        }
        return res.json();
    },
};
