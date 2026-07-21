import type { RunEvent } from './types';

export interface EventState { items: RunEvent[]; lastEventId: number }
export type EventAction = RunEvent | { type: '__reset__'; items: RunEvent[] };

export function eventReducer(state: EventState, action: EventAction): EventState {
  if (action.type === '__reset__' && 'items' in action && Array.isArray(action.items)) {
    return initialEventState(action.items as RunEvent[]);
  }
  const event = action as RunEvent;
  const eventId = typeof event.event_id === 'number' ? event.event_id : 0;
  if (eventId > 0 && eventId <= state.lastEventId) return state;
  return { items: [...state.items, event], lastEventId: Math.max(state.lastEventId, eventId) };
}

export function initialEventState(items: RunEvent[]): EventState {
  return items.reduce<EventState>((state, event) => eventReducer(state, event), { items: [], lastEventId: 0 });
}
