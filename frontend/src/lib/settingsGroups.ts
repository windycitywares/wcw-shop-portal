/** The settings groups, in the order they appear on the settings page. Shared so the header menu and the
 *  settings page stay in sync. */
export const SETTINGS_GROUPS: { id: string; label: string }[] = [
  { id: "shipping", label: "Shipping" },
  { id: "tax", label: "Sales tax" },
  { id: "payments", label: "Payments" },
  { id: "welcome", label: "Welcome offer" },
  { id: "cart_recovery", label: "Cart reminders" },
  { id: "reviews", label: "Reviews" },
  { id: "analytics", label: "Analytics" },
  { id: "digest", label: "Weekly email" },
  { id: "general", label: "General" },
];
