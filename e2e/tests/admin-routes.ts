/** Every admin page. New admin pages are added here, and the tests below cover them automatically. */
export const ADMIN_ROUTES: { path: string; heading: RegExp; name: string }[] = [
  { path: "/admin", heading: /./, name: "dashboard" },
  { path: "/admin/orders", heading: /^Orders$/, name: "orders" },
  { path: "/admin/promotions", heading: /^Promotions$/, name: "promotions" },
  { path: "/admin/promotions?tab=coupons", heading: /^Promotions$/, name: "promotions-coupons" },
  { path: "/admin/promotions?tab=offers", heading: /^Promotions$/, name: "promotions-offers" },
  { path: "/admin/customers", heading: /^Customers$/, name: "customers" },
  { path: "/admin/campaigns", heading: /^Email campaigns$/, name: "campaigns" },
  { path: "/admin/carts", heading: /^Abandoned carts$/, name: "carts" },
  { path: "/admin/products", heading: /^Products$/, name: "products" },
  { path: "/admin/products/new", heading: /^New product$/, name: "product-new" },
  { path: "/admin/categories", heading: /^Categories$/, name: "categories" },
  { path: "/admin/import", heading: /^Import and export$/, name: "import" },
  { path: "/admin/users", heading: /^Team and customers$/, name: "users" },
];
