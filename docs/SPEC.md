# E-Commerce Platform Specification Document

## 1. Project Overview
Build a full-featured, modular, and SEO-friendly enterprise e-commerce platform. The system must support deep categorization, dynamic product attributes, and a comprehensive headless admin dashboard. It must be fully responsive, adhere strictly to WCAG accessibility standards, and use a template-based layout for easy future UI iterations.

## 2. Technology Stack
*   **Frontend:** Next.js (App Router), React, Tailwind CSS, TypeScript.
*   **UI Components:** Modular, template-based (Header, Content, Footer). Recommend using headless accessible components (e.g., Radix UI or shadcn/ui) styled with Tailwind.
*   **Backend:** Python (FastAPI) - strictly typed, async, providing a RESTful JSON API. Or any recommended framework.
*   **Database:** PostgreSQL (utilizing `JSONB` for dynamic attributes and `ltree` for hierarchical categories).
*   **ORM:** SQLAlchemy (Async) or SQLModel.

## 3. Architecture & Layout (Template-Based)
The frontend must follow a strict modular template architecture to allow future theme swaps:
*   **Main Layout (`app/layout.tsx`):**
    *   `<Header />`: Contains branding, primary navigation (dynamic from category tree), search bar, and cart icon/drawer.
    *   `<main>`: The dynamic content area injected via route segments.
    *   `<Footer />`: Newsletter signup, secondary links, social icons, legal.
*   **Component Modularity:** All UI elements (Buttons, Cards, Modals, Inputs) must be abstracted into a `components/ui/` directory.

## 4. Role-Based Access Control (RBAC)
The system must support JWT-based authentication with the following distinct roles:
1.  **Admin:** Superuser. Full access to system settings, user management, financial data, and all catalog features.
2.  **Publisher:** Can review, edit, approve, and publish products, categories, and content/blogs. Cannot alter system settings or manage admin users.
3.  **Author:** Can create and draft new products or content, but cannot set them to "Live/Published".
4.  **User (Customer):** Standard storefront user. Can manage their profile, view order history, save addresses, and manage a wishlist.

## 5. Database Schema & Data Modeling
*   **Categories:** Must use the Adjacency List model with materialized paths for infinite depth (e.g., `Home > Decor > Vases`).
*   **Products:** 
    *   Core columns: `id`, `sku`, `title`, `base_price`, `stock_status`, `category_id`.
    *   Dynamic columns: `attributes` (`JSONB`). This handles unique data per product (e.g., sizes, colors, engraving options, dimensions) without altering the schema.
*   **Orders:** Track line items, totals, tax, shipping status, and payment intent IDs.
*   **Users:** Store authentication data, role ID, and profile references.

## 6. Core E-Commerce Features (Latest Standards)
*   **Catalog & Navigation:** Mega-menu generated dynamically from the category tree.
*   **Filtering & Sorting:** Faceted search (Filter by price, category, and dynamic JSONB attributes like "Material" or "Color").
*   **Cart & Checkout:** Persistent cart (stored in DB for logged-in users, local storage for guests). Multi-step checkout (Address -> Shipping -> Payment Review).
*   **Variants:** Products can have parent-child relationships for variants (e.g., Shirt: Parent. Red/Large: Child variant with specific SKU/Price).

## 7. Non-Functional Requirements
### A. Accessibility (a11y)
*   Must pass WCAG 2.1 AA standards.
*   Full keyboard navigability (focus states clearly visible via Tailwind `focus-visible`).
*   Screen-reader friendly: Proper use of ARIA labels, semantic HTML (`<nav>`, `<article>`, `<aside>`), and `alt` text for all product imagery.

### B. SEO Optimization
*   Server-Side Rendering (SSR) / Static Site Generation (SSG) via Next.js for all product and category pages.
*   Dynamic metadata, title tags, and canonical URLs.
*   Auto-generated `sitemap.xml` and `robots.txt`.
*   JSON-LD Structured Data for Products, Breadcrumbs, and Organization.

### C. Deployment & Hosting (Shared Hosting Compatibility)
*While modern stacks prefer containerization (Docker) or serverless (Vercel), the architecture must account for constrained environments:*
*   **Backend:** Must be runnable via standard WSGI/ASGI gateways (e.g., Passenger on cPanel) so Python can run on shared hosting with terminal access.
*   **Frontend:** The Next.js app should support `output: 'standalone'` for easy deployment via a simple Node.js server on cPanel, or `output: 'export'` if dynamic server rendering needs to be sacrificed for standard static shared hosting.
*   **Database:** Standard PostgreSQL connection string compatibility.
*   **Code should be well architecture - OOPS / Solid Principal / Easy to maintain and upgrrde.

## 8. Admin Dashboard Requirements
A protected route group (e.g., `/admin`) containing:
*   **Dashboard:** High-level metrics (sales, active carts, low stock).
*   **Catalog Management:** CRUD operations for Products (with a dynamic JSON attribute builder UI) and Categories (drag-and-drop tree reordering).
*   **Order Management:** Update order statuses, process refunds, view customer details.
*   **User Management:** Assign roles (Admin, Publisher, Author) and manage customer accounts.
*   **Settings:** Global configurations (shipping rates, tax zones, site name, logo upload).
*   ** product management through UI / excel 
*   ** open for full fetured ecommerce platform 

## Next Steps for AI Agent:
1. Initialize the Next.js frontend with Tailwind and modular layout structure.
2. Initialize the FastAPI backend and configure the PostgreSQL connection.
3. Generate the core ORM models (User, Category, Product).
4. Implement JWT authentication and RBAC middleware.

## Suggestions:
*  Use best features and Ui to keep it fast, scalable.