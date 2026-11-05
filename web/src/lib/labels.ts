import { groupDigits } from "./format";

/** Plain-English names for the extracted fields. Unknown names fall back to the raw name. */
const FIELD_LABELS: Record<string, string> = {
  supplier: "Supplier",
  quotation_no: "Quotation number",
  date: "Quotation date",
  item_code: "Item code",
  description: "Description",
  qty: "Quantity",
  unit: "Unit",
  unit_price: "Unit price (BDT)",
  subtotal: "Subtotal (BDT)",
  vat_amount: "VAT amount (BDT)",
  total: "Total (BDT)",
  vat_shown_separately: "VAT shown separately",
  tin: "TIN (tax number)",
  bin: "BIN (business number)",
  advance_pct: "Advance payment (%)",
  payment_days: "Payment terms",
  delivery_days: "Delivery time (days)",
  penalty_pct_per_week: "Late-delivery penalty (% per week)",
  validity_days: "Quote valid for (days)",
};

const MONEY = new Set(["unit_price", "subtotal", "vat_amount", "total"]);
const COUNT = new Set(["qty"]);

export const fieldLabel = (name: string): string => FIELD_LABELS[name] ?? name.replaceAll("_", " ");

export function fieldValue(name: string, value: string | null): string {
  if (value === null) return "Not found";
  if (name === "vat_shown_separately") return value === "True" ? "Yes" : "No";
  return MONEY.has(name) || COUNT.has(name) ? groupDigits(value) : value;
}

const ARITHMETIC_LABELS: Record<string, string> = {
  line_total: "Quantity × unit price = line total",
  subtotal: "Line totals add up to the subtotal",
  vat: "VAT is 15% of the subtotal",
  total: "Subtotal + VAT = total",
};

export const arithmeticLabel = (check: string): string =>
  ARITHMETIC_LABELS[check] ?? check.replaceAll("_", " ");

const FIELD_STATUS: Record<string, string> = {
  OK: "Verified",
  MISSING: "Not found",
  UNVERIFIED: "Quote not verified",
  CONFLICT: "Readers disagree",
};

export const fieldStatusLabel = (status: string): string => FIELD_STATUS[status] ?? status;
