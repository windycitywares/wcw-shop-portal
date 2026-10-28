/** Where the CRM lives. Subscribers and email campaigns are worked there; the shop only shows them. */
export const CRM_URL = (process.env.NEXT_PUBLIC_CRM_URL || "https://crm.windycitywares.com").replace(/\/$/, "");

export function crmLink(path = ""): string {
  return `${CRM_URL}${path}`;
}
