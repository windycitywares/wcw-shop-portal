/** Short, plain-language help for each admin screen. Shown from the "?" button in the header. */

export interface HelpEntry {
  title: string;
  body: string[];
}

const HELP: Record<string, HelpEntry> = {
  "/admin": {
    title: "Dashboard",
    body: [
      "A quick read of how the shop is doing: orders placed, revenue, and what needs your attention today.",
      "The numbers update as orders come in. Click any card to open the list behind it.",
    ],
  },
  "/admin/analytics": {
    title: "Analytics",
    body: [
      "Sales, revenue and traffic over a date range. Use it to spot trends, not to answer 'what should I do right now'.",
      "Export any chart's underlying rows from the report pages.",
    ],
  },
  "/admin/orders": {
    title: "Orders",
    body: [
      "Every order, newest first. Search by number, customer name or email. Open one to ship, mark delivered, refund or cancel.",
      "Refunds go through the payment provider when one is configured; otherwise record the money you returned by hand.",
      "An order marked 'waiting for payment' (pay-later) is no longer offered at checkout — card only.",
    ],
  },
  "/admin/products": {
    title: "Products",
    body: [
      "Your catalog. Drafts are invisible to shoppers; published products appear in the shop.",
      "Variants (sizes, colours) are separate products linked to a parent. Stock is tracked per variant.",
      "Use the 'Publish' button to make a product visible; unpublish to hide it without deleting.",
    ],
  },
  "/admin/categories": {
    title: "Categories",
    body: [
      "The tree shoppers browse. Drag to reorder; a category with sub-categories can't be deleted.",
      "Products belong to one category. Moving a category moves its products with it.",
    ],
  },
  "/admin/import": {
    title: "Import and export",
    body: [
      "Bring in a CSV (Etsy exports work) to create or update products. Re-importing updates existing rows by their SKU.",
      "Export the whole catalog to Excel whenever you want a backup or a bulk edit.",
    ],
  },
  "/admin/reviews": {
    title: "Reviews",
    body: [
      "Moderate reviews shoppers left. Approve to publish, reject to hide, reply to thank or answer.",
      "Only shoppers who bought the product get a 'verified' badge. Helpful votes are counted per review.",
    ],
  },
  "/admin/customers": {
    title: "Customers",
    body: [
      "Shoppers grouped by value (RFM). Click one to see their orders and addresses.",
      "Buyers lists everyone who paid, guests included; Accounts lists every shopper who signed up.",
    ],
  },
  "/admin/messages": {
    title: "Messages",
    body: [
      "Contact-form messages. Mark as answered or spam; replying sends an email from the shop.",
    ],
  },
  "/admin/notifications": {
    title: "Activity",
    body: [
      "Everything from the last 30 days you may need to act on: new orders and refunds, contact messages, stock requests, reviews, sign-ups and failed backups. You only see the kinds your role can work on.",
      "The bell in the top bar shows the newest; opening this page marks them as seen. Use the tabs to work through one kind at a time, and select an item to open it where it's handled.",
    ],
  },
  "/admin/stock-requests": {
    title: "Stock requests",
    body: [
      "'Notify me' requests from shoppers. When stock returns, run the back-in-stock job to email them.",
      "Special requests (a size or colour you don't stock) are listed separately.",
    ],
  },
  "/admin/campaigns": {
    title: "Email campaigns",
    body: [
      "Draft a newsletter, pick the audience (all subscribers, customers, or a segment), and send when ready.",
      "Campaigns respect each subscriber's unsubscribe choice.",
    ],
  },
  "/admin/etsy": {
    title: "Etsy dashboard",
    body: [
      "How the Etsy shop is doing over the dates you pick, compared with the period just before: orders, revenue, profit, margin, average order and days to ship.",
      "Narrow it to one product or one supplier with the filters. 'Show as table' under each chart gives the exact numbers.",
      "Profit and margin only count orders that have a purchase cost, and don't include Etsy fees yet (phase 2). The note at the top says how many orders are counted.",
    ],
  },
  "/admin/etsy/orders": {
    title: "Etsy orders",
    body: [
      "Every paid Etsy order arrives here by itself within about five minutes. Etsy's details (items, prices, address) can't be changed here.",
      "Open an order to enter what you paid, the supplier, the shipping cost and tracking. Profit is worked out from those; anything missing is listed under Profit.",
      "Needs attention lists orders that are waiting too long, late for Etsy's ship-by date, missing a cost, or losing money.",
      "Etsy sets New, Cancelled, Shipped and Delivered by itself and never moves an order backwards. Everything else (Purchased, Issue reported, Return requested…) is yours. Every change is kept in the order's History.",
    ],
  },
  "/admin/etsy/payments": {
    title: "Supplier payments",
    body: [
      "What you owe each supplier for Etsy orders: purchase cost + shipping cost. An order is Pending once its purchase cost is entered, and Settled when an admin marks it paid.",
      "Tick several pending orders and press Mark paid to settle a whole supplier invoice at once (one date and reference). For one order you can enter a different amount.",
      "A payment never changes the order's costs. Undo puts it back to Pending; both are kept in the order's history.",
      "Export CSV or Excel for your books, or Print or save PDF for a statement. Exports follow the tab and filters you have chosen.",
    ],
  },
  "/admin/etsy/products": {
    title: "Etsy listings",
    body: [
      "Your Etsy listings, read from Etsy every 15 minutes. Change listings on Etsy itself; this list follows.",
      "Click a listing to add your default supplier, purchase cost and notes. New orders start with that cost, so profit is right from day one.",
      "A listing that disappears from Etsy is marked “Removed from Etsy”, not deleted, so old orders still make sense.",
    ],
  },
  "/admin/carts": {
    title: "Abandoned carts",
    body: [
      "Carts shoppers left behind. The reminder job emails the ones that are 'reachable' (an address was kept).",
      "In Settings you can choose to email everyone who leaves an address, not only those who tick the box.",
    ],
  },
  "/admin/promotions": {
    title: "Promotions",
    body: [
      "Coupons and automatic discounts. Set the value, who it applies to, and when it expires.",
      "Coupons can be single-use or reusable; automatic discounts apply at checkout without a code.",
    ],
  },
  "/admin/settings": {
    title: "Store settings",
    body: [
      "Everything about how the shop behaves: shipping, tax, payments, emails, analytics, cart reminders, welcome offers.",
      "Changes are saved per group. Sensitive values (API keys) stay in the server's .env file.",
    ],
  },
  "/admin/team": {
    title: "Team",
    body: [
      "Staff accounts: admins, publishers and authors. Add a team member here; shoppers sign up themselves.",
      "Change a role, switch an account off, set a new password, or edit a name or email. You can't change your own role or disable yourself.",
    ],
  },
  "/admin/users": {
    title: "Customer accounts",
    body: [
      "Every shopper account. Edit a customer's name or email, set a new password, or switch an account off.",
      "Team members are on the Team page.",
    ],
  },
  "/admin/audit": {
    title: "Audit log",
    body: [
      "A record of who changed what in the admin. Useful when something looks different and you want to know who did it.",
    ],
  },
  "/admin/environment": {
    title: "Test mode",
    body: [
      "Work on a copy of the live data so you can test changes without touching real orders or customers.",
      "Only staff and the addresses you list can sign in on the copy. Emails go to the test inbox (or nowhere).",
      "Switch back to live and delete the copy when you're done.",
    ],
  },
  "/admin/backups": {
    title: "Backups",
    body: [
      "Database backups, automatic and on demand. A failed backup shows up in the notification bell.",
    ],
  },
  "/admin/deployments": {
    title: "Deployments",
    body: [
      "When the server looks for updates: automatic, scheduled, or paused. 'Deploy now' runs one immediately.",
    ],
  },
};

export function helpFor(pathname: string): HelpEntry | null {
  const keys = Object.keys(HELP).sort((a, b) => b.length - a.length);
  const match = keys.find((k) => pathname === k || pathname.startsWith(`${k}/`));
  return match ? HELP[match] : null;
}
