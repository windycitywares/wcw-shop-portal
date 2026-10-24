/** The admin wiki: plain-language help for staff. Shown only inside /admin (never linked from the public site). */
export interface WikiArticle { id: string; title: string; summary: string; paragraphs: string[] }

export const ADMIN_WIKI: WikiArticle[] = [
  {
    "id": "start",
    "title": "Getting started",
    "summary": "Find your way around the admin.",
    "paragraphs": [
      "The left menu groups the work: Sales (orders, reports, abandoned carts), Customers, Marketing (promotions, email campaigns, subscribers), Catalog (products, categories, import, reviews) and Settings.",
      "You only see the menu items your role allows. If something is missing, ask an admin to change your role in Settings → Team.",
      "The strip above every page (Dashboard › section › page) shows where you are; click any part of it to go back. Inside Settings the left menu switches to the settings list, with a Back to dashboard button at the top.",
      "Changes you save are live straight away. To practise safely, turn on Test mode (Settings → Test mode)."
    ]
  },
  {
    "id": "orders",
    "title": "Orders and customers",
    "summary": "Day-to-day work.",
    "paragraphs": [
      "Orders lists every order. Open one to see items, address and payment, and to mark it shipped with a tracking number; the customer is emailed automatically.",
      "Customers shows everyone who has ordered or signed up. Subscribers are people on the newsletter list; you can pause or resume a subscriber.",
      "Messages holds what customers wrote through the Contact page. Reply from there.",
      "Abandoned carts shows people who left items behind; Cart reminders in Settings decides whether they are emailed."
    ]
  },
  {
    "id": "catalog",
    "title": "Products and catalog",
    "summary": "Keeping the shop fresh.",
    "paragraphs": [
      "Products: add or edit a product, set price, stock and photos, and publish it. Drafts are invisible to shoppers.",
      "Categories organise the menu. Import and export brings in your Etsy listings from a file and exports the catalog.",
      "Reviews: approve or hide customer reviews (see Settings → Reviews for the rules)."
    ]
  },
  {
    "id": "marketing",
    "title": "Promotions and email campaigns",
    "summary": "Bring people back.",
    "paragraphs": [
      "Promotions: create discount codes and automatic offers, with start and end dates.",
      "Email campaigns: write a newsletter and send it to subscribers. Every email carries an unsubscribe link; people who unsubscribe are never emailed again.",
      "Check Email sending first (Settings) so campaigns can leave the building."
    ]
  },
  {
    "id": "set-shipping",
    "title": "Settings → Shipping",
    "summary": "What customers pay and wait.",
    "paragraphs": [
      "Set the flat or per-order shipping price, the order total above which shipping is free, and the number of days you quote for delivery.",
      "These appear in the cart, at checkout and on the Shipping help page, so change them here only."
    ]
  },
  {
    "id": "set-tax",
    "title": "Settings → Sales tax",
    "summary": "Collecting tax.",
    "paragraphs": [
      "Switch tax collection on or off, enter the rate as a percentage, and list the states where you must charge it.",
      "Ask your accountant for the correct rate. Stripe’s own tax features are separate and are not used here."
    ]
  },
  {
    "id": "set-payments",
    "title": "Settings → Payments",
    "summary": "Card payments.",
    "paragraphs": [
      "Card payments run through Stripe. Live keys are added on the server by the site owner; this page controls the wording shown when an order is waiting for payment.",
      "While in Test mode no real money moves."
    ]
  },
  {
    "id": "set-welcome",
    "title": "Settings → Welcome offer",
    "summary": "The code new subscribers get.",
    "paragraphs": [
      "Choose whether new subscribers receive a personal discount code, how much it is worth and how long it lasts.",
      "Only people who have not ordered yet are given a code. Edit the email wording in Email templates."
    ]
  },
  {
    "id": "set-cart",
    "title": "Settings → Cart reminders",
    "summary": "Left-behind carts.",
    "paragraphs": [
      "Turn reminders on, choose how long after leaving the cart the email is sent, and whether a small discount is included.",
      "Each person gets at most the number of reminders you set, and never after they unsubscribe."
    ]
  },
  {
    "id": "set-reviews",
    "title": "Settings → Reviews",
    "summary": "Customer reviews.",
    "paragraphs": [
      "Decide whether reviews appear immediately or wait for your approval, and whether only buyers may review.",
      "Approve waiting reviews under Catalog → Reviews."
    ]
  },
  {
    "id": "set-analytics",
    "title": "Settings → Analytics",
    "summary": "Visit statistics.",
    "paragraphs": [
      "Visitors are counted only if they accept the cookie banner. Switch statistics off here if you do not want any.",
      "Reports appear under Analytics in the main menu."
    ]
  },
  {
    "id": "set-scripts",
    "title": "Settings → Tracking code",
    "summary": "Google Analytics, Tag Manager and other snippets.",
    "paragraphs": [
      "Paste the snippet exactly as the service gives it. Put it in Header code if they say “in the head”, and in Footer code if they say “before the closing body tag”.",
      "Leave “Wait for the visitor to accept the cookie banner” on unless you are sure the snippet is not tracking people. Visitors who decline are then never tracked by it.",
      "Only paste code from services you trust: it runs on every page. It is never added to this admin. To remove a snippet, clear its box and save.",
      "Search engines that read page source (for example for a Search Console verification tag) may not see tags added this way; use the service’s other verification method if it fails."
    ]
  },
  {
    "id": "set-digest",
    "title": "Settings → Weekly email",
    "summary": "Monday summary.",
    "paragraphs": [
      "Turn the weekly summary on and choose who receives it. It lists last week’s orders, revenue and top products."
    ]
  },
  {
    "id": "set-general",
    "title": "Settings → General",
    "summary": "Store-wide switches.",
    "paragraphs": [
      "The announcement bar shows a short message at the top of every page, for example a sale or holiday delay.",
      "Order alerts decide who is emailed when an order arrives. Checkout rules cover guest checkout and similar options."
    ]
  },
  {
    "id": "email",
    "title": "Email sending and templates",
    "summary": "Making email work.",
    "paragraphs": [
      "Email sending: enter the From name and address and the mail server details your host gave you (host, port, username, password). The password is stored encrypted and is never shown again.",
      "Press Send test email to yourself. If it fails, the message says why; the most common causes are a wrong password or port.",
      "Email templates: change the wording of welcome, password-reset and order emails. Keep the {placeholders}; they are filled in for each customer. Use Preview before saving, and Reset to restore the original."
    ]
  },
  {
    "id": "team",
    "title": "Team and permissions",
    "summary": "Who can do what.",
    "paragraphs": [
      "Team lists everyone who can sign in. Invite a person, choose their role, or disable them; a disabled person sees a clear message when they try to sign in.",
      "Give people the smallest role they need. Only admins can change settings."
    ]
  },
  {
    "id": "safety",
    "title": "Audit log, Test mode, Backups, Deployments",
    "summary": "Safety tools.",
    "paragraphs": [
      "Audit log: who changed what and when. Search it if something looks wrong.",
      "Test mode: a copy of the shop data to practise on. Emails go only to the test inbox you set.",
      "Backups: save a copy before big changes, and restore one if needed. Restoring replaces current data, so you are asked to confirm.",
      "Deployments: publishes the latest code to the live shop. Choose automatic times or press Deploy now. Nothing changes on the public site until it has deployed."
    ]
  }
];
