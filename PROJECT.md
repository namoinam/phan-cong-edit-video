# Project: Style Synchronization for namoinam.com

## Architecture
This project consists of the main landing page and 4 internal management sub-pages. The sub-pages contain administrative scripts and dynamic tables that use local files (e.g. `products.json`) or local storage.
The goal is to modernize the user interface of all 4 sub-pages to match the main landing page's clean "Lark Style" design while keeping all underlying JavaScript logic, forms, dynamic formulas, tables, and events intact.

## Code Layout
- `index.html` — Root landing page
- `style.css` — Root stylesheet defining the visual design system (fonts, colors, variables)
- `script.js` — Root script
- `/quan-ly-team/index.html` — Portal to management sub-pages
- `/theo-doi-san-pham-edit/index.html` — Product tracking table with import/export features
- `/phan-cong-edit-video/index.html` — Daily editing task schedule card layout
- `/bang-tinh-luong-thuong/index.html` — Salary calculation page with dynamic form, breakdown tables, and QR generation

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration | Inspect root `index.html` and `style.css` to define Lark Style components and analyze sub-page scripts | None | DONE |
| 2 | Implementation | Synchronize styles on the 4 sub-pages: fonts, header/nav, button/card, and colors | 1 | DONE |
| 3 | Review & Challenge | Independently review styling and verify that 100% of the functionality remains operational | 2 | DONE |
| 4 | Integrity Audit | Perform static/dynamic forensic integrity verification to rule out cheating/broken logic | 3 | DONE |

## Interface Contracts
- **Visual Palette**: Primary Lark Blue `#1456F0` (with corresponding hover and background classes), white, soft gray `#F7F8FA` backgrounds, and clean borders `#E0E5EB`.
- **Typography**: Font family 'Be Vietnam Pro', system-ui, sans-serif. Load Google Font stylesheets: `https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;500;600;700;800;900&display=swap`.
- **Navigation/Header**: Every sub-page must have a clean header matching the landing page navbar, including a cohesive "Back to landing page" link or button.
- **Functionality Isolation**: No script blocks, IDs, classes used in JavaScript queries, or state logic may be modified or deleted. All forms, tables, checkboxes, number inputs, local JSON paths, and clipboard buttons must continue to work exactly as they do currently.
