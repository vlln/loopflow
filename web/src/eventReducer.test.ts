import { eventReducer, initialEventState } from './eventReducer';

describe('event reducer', () => {
  it('deduplicates replayed persisted event ids', () => {
    const initial = initialEventState([{ type: 'log', event_id: 7 }, { type: 'log', event_id: 8 }]);
    const replayed = eventReducer(initial, { type: 'log', event_id: 8 });
    const next = eventReducer(replayed, { type: 'log', event_id: 9 });
    expect(next.items.map((item) => item.event_id)).toEqual([7, 8, 9]);
    expect(next.lastEventId).toBe(9);
  });
});
