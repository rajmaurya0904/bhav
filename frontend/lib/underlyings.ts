// Kept in sync with bhav/data/underlyings.py.
// Lot sizes reflect the NSE/BSE revisions effective from the January 2026
// expiry cycle. The frontend does not fetch these from the API on every load
// so the form stays functional even when the backend is offline.

export type UnderlyingSpec = {
  key: string;
  display: string;
  lot_size: number;
  atm_step: number;
};

export const UNDERLYINGS: UnderlyingSpec[] = [
  { key: "NSE_INDEX|Nifty 50",          display: "NIFTY 50",      lot_size: 65,  atm_step: 50  },
  { key: "NSE_INDEX|Nifty Bank",        display: "BANK NIFTY",    lot_size: 25,  atm_step: 100 },
  { key: "NSE_INDEX|Nifty Fin Service", display: "FIN NIFTY",     lot_size: 65,  atm_step: 50  },
  { key: "NSE_INDEX|NIFTY MID SELECT",  display: "MIDCAP NIFTY",  lot_size: 120, atm_step: 25  },
  { key: "NSE_INDEX|Nifty Next 50",     display: "NIFTY NEXT 50", lot_size: 25,  atm_step: 100 },
  { key: "BSE_INDEX|SENSEX",            display: "SENSEX",        lot_size: 20,  atm_step: 100 },
  { key: "BSE_INDEX|BANKEX",            display: "BANKEX",        lot_size: 30,  atm_step: 100 },
  { key: "BSE_INDEX|SENSEX 50",         display: "SENSEX 50",     lot_size: 60,  atm_step: 100 },
];

export function lotSizeFor(key: string): number {
  return UNDERLYINGS.find((u) => u.key === key)?.lot_size ?? 65;
}
