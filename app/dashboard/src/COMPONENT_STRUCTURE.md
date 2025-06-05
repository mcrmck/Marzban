# Component Organization Guide

This document outlines the reorganized component structure for the Marzban Dashboard, which supports both an admin panel and client portal.

## 📁 Directory Structure

```
src/
├── components/
│   ├── admin/                    # Admin-only components
│   ├── client/                   # Client-only components  
│   └── shared/                   # Shared components (used by both)
├── pages/
│   ├── admin/                    # Admin page components
│   └── client/                   # Client page components
├── app/
│   ├── admin/                    # Admin routing and app setup
│   └── shared/                   # Shared app components (login, etc.)
├── lib/                          # Shared utilities, stores, APIs
│   ├── api/                      # API clients
│   ├── stores/                   # State management
│   ├── utils/                    # Utility functions
│   └── types/                    # TypeScript types
└── theme/                        # Theme configurations
```

## 🎯 Component Categories

### Admin Components (`components/admin/`)
Components exclusive to the admin panel for system management:

- **User Management**: `UserDialog.tsx`, `UsersTable.tsx`, `UsersModal.tsx`
- **Node Management**: `NodesTable.tsx`, `NodeForm.tsx`, `EditNodeDialog.tsx`, `DeleteNodeModal.tsx`
- **Certificate Management**: `CertificateManagement.tsx`
- **System Settings**: `CoreSettingsModal.tsx`, `Statistics.tsx`
- **Data Management**: `ResetAllUsageModal.tsx`, `ResetUserUsageModal.tsx`, `RevokeSubscriptionModal.tsx`
- **UI Utilities**: `Filters.tsx`, `Pagination.tsx`, `UsageFilter.tsx`, `Header.tsx`
- **JSON Configuration**: `JsonEditor/` (directory with index.tsx, styles.css, themes.js)

### Client Components (`components/client/`)
Components exclusive to the client portal for end-user functionality:

- **App Setup**: `ClientAppInitializer.tsx`
- **Navigation**: `ClientHeader.tsx`
- **Layout**: `ClientLayout.tsx`

### Shared Components (`components/shared/`)
Components used by both admin and client applications:

- **UI Components**: `StatusBadge.tsx`, `OnlineBadge.tsx`, `OnlineStatus.tsx`
- **Dialogs**: `QRCodeDialog.tsx`
- **Forms**: `Textarea.tsx`
- **Navigation**: `Language.tsx`, `Footer.tsx`
- **Node Selection**: `ClientNodeSelector.tsx`
- **UI System**: `ui/` (toaster.tsx, index.ts)

## 🚀 Usage Guidelines

### For Admin Components
```typescript
// Importing admin components
import { UsersTable } from '../components/admin/UsersTable';
import { NodeForm } from '../components/admin/NodeForm';
import { CertificateManagement } from '../components/admin/CertificateManagement';
```

### For Client Components
```typescript
// Importing client components
import { ClientHeader } from '../components/client/ClientHeader';
import { ClientLayout } from '../components/client/ClientLayout';
```

### For Shared Components
```typescript
// Importing shared components (can be used by both admin and client)
import { StatusBadge } from '../components/shared/StatusBadge';
import { Language } from '../components/shared/Language';
import { Footer } from '../components/shared/Footer';
```

## 📋 Rules and Best Practices

### 1. **Component Placement Rules**
- **Admin-only features** → `components/admin/`
- **Client-only features** → `components/client/`
- **Reusable UI components** → `components/shared/`
- **Full page components** → `pages/admin/` or `pages/client/`

### 2. **Import Path Conventions**
- Use relative imports from the same category: `import { Helper } from './Helper';`
- Use proper relative paths for cross-category imports: `import { Badge } from '../../shared/StatusBadge';`
- Avoid absolute imports for components (use for lib utilities only)

### 3. **Naming Conventions**
- **Admin components**: Descriptive names focused on management (e.g., `UsersTable`, `NodeForm`)
- **Client components**: Prefixed with "Client" (e.g., `ClientHeader`, `ClientLayout`)
- **Shared components**: Generic, reusable names (e.g., `StatusBadge`, `Language`)

### 4. **Dependencies**
- **Admin components** can import from `shared/` but NOT from `client/`
- **Client components** can import from `shared/` but NOT from `admin/`
- **Shared components** should NOT import from `admin/` or `client/`
- All components can import from `lib/` utilities

## 🔧 Development Workflow

### Adding New Components

1. **Determine the category**:
   - Is it admin-only? → `components/admin/`
   - Is it client-only? → `components/client/`
   - Can it be reused? → `components/shared/`

2. **Follow naming conventions**:
   - Admin: `FeatureManagement.tsx`, `FeatureTable.tsx`
   - Client: `ClientFeature.tsx`, `ClientFeaturePanel.tsx`
   - Shared: `FeatureBadge.tsx`, `FeatureSelector.tsx`

3. **Update imports correctly**:
   - Check relative paths based on component location
   - Use shared components when possible to avoid duplication

### Refactoring Existing Components

1. **Identify the component's scope**:
   - Used only by admin? Move to `admin/`
   - Used only by client? Move to `client/`
   - Used by both? Move to `shared/`

2. **Update all import paths** throughout the codebase
3. **Test both admin and client portals** after changes

## 🎨 Theme and Styling

- **Admin theme**: `theme/adminTheme.ts`
- **Client theme**: `theme/clientTheme.ts`
- **Base theme**: `theme/base.ts`

Components automatically inherit the appropriate theme based on which application loads them.

## 🧪 Testing

When making changes to the component structure:

1. **Test admin portal**: `http://localhost:3000/admin/`
2. **Test client portal**: `http://localhost:3001/`
3. **Verify authentication flows** work for both portals
4. **Check responsive behavior** for both interfaces

## 🚨 Migration Notes

This structure was reorganized from a previously mixed component directory. Key changes:

- **Removed duplicate**: `/apps/` architecture (unused)
- **Cleaned up**: Duplicate constants and dead code
- **Consolidated**: Shared utilities in `/lib/`
- **Separated**: Admin vs client specific functionality

For any questions about component placement or structure, refer to this guide or examine the existing codebase patterns.