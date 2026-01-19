import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import RoleGuard from './components/RoleGuard';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import UserDetail from './pages/UserDetail';
import Profile from './pages/Profile';
import Settings from './pages/Settings';

// Marketplace pages
import MarketplaceIndex from './pages/marketplace/index';
import Catalog from './pages/marketplace/Catalog';
import Inventory from './pages/marketplace/Inventory';
import Deployments from './pages/marketplace/Deployments';
import Clusters from './pages/marketplace/Clusters';
import Repositories from './pages/marketplace/Repositories';
import Updates from './pages/marketplace/Updates';
import CustomManifest from './pages/marketplace/CustomManifest';

function App() {
  const { isAuthenticated, isLoading, checkAuth } = useAuth();

  // Check authentication status on app mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-950">
        <div className="text-gold-400 text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />

      {/* Protected routes with layout */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        {/* Dashboard - all authenticated users */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/dashboard" element={<Navigate to="/" replace />} />

        {/* Profile - all authenticated users */}
        <Route path="/profile" element={<Profile />} />

        {/* Settings - Maintainer and Admin */}
        <Route
          path="/settings"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <Settings />
            </RoleGuard>
          }
        />

        {/* User management - Admin only */}
        <Route
          path="/users"
          element={
            <RoleGuard allowedRoles={['admin']}>
              <Users />
            </RoleGuard>
          }
        />
        <Route
          path="/users/:id"
          element={
            <RoleGuard allowedRoles={['admin']}>
              <UserDetail />
            </RoleGuard>
          }
        />

        {/* Marketplace routes - Maintainer and Admin */}
        <Route
          path="/marketplace"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <Catalog />
            </RoleGuard>
          }
        />
        <Route
          path="/marketplace/inventory"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <Inventory />
            </RoleGuard>
          }
        />
        <Route
          path="/marketplace/deployments"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <Deployments />
            </RoleGuard>
          }
        />
        <Route
          path="/marketplace/updates"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <Updates />
            </RoleGuard>
          }
        />
        <Route
          path="/marketplace/manifest"
          element={
            <RoleGuard allowedRoles={['admin', 'maintainer']}>
              <CustomManifest />
            </RoleGuard>
          }
        />

        {/* Marketplace Admin-only routes */}
        <Route
          path="/marketplace/clusters"
          element={
            <RoleGuard allowedRoles={['admin']}>
              <Clusters />
            </RoleGuard>
          }
        />
        <Route
          path="/marketplace/repositories"
          element={
            <RoleGuard allowedRoles={['admin']}>
              <Repositories />
            </RoleGuard>
          }
        />
      </Route>

      {/* Catch all - redirect to dashboard or login */}
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? '/' : '/login'} replace />}
      />
    </Routes>
  );
}

export default App;
