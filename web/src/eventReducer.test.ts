import { eventReducer, initialEventState } from './eventReducer';

describe('event reducer', () => {
  it('deduplicates replayed persisted event ids', () => {
    const initial = initialEventState([{ type: 'log', event_id: 7 }, { type: 'log', event_id: 8 }]);
    const replayed = eventReducer(initial, { type: 'log', event_id: 8 });
    const next = eventReducer(replayed, { type: 'log', event_id: 9 });
    expect(next.items.map((item) => item.event_id)).toEqual([7, 8, 9]);
    expect(next.lastEventId).toBe(9);
  });

  it('AC-016-E-2: applying the same event_id twice changes state only once', () => {
    const initial = initialEventState([]);
    const once = eventReducer(initial, { type: 'agent_message', event_id: 5, message: 'hello' });
    const twice = eventReducer(once, { type: 'agent_message', event_id: 5, message: 'hello' });
    expect(twice).toBe(once);
    expect(twice.items).toHaveLength(1);
    expect(twice.lastEventId).toBe(5);
    // a later event still applies after a duplicate
    const later = eventReducer(twice, { type: 'agent_message', event_id: 6, message: 'next' });
    expect(later.items.map((item) => item.event_id)).toEqual([5, 6]);
  });
});
