import { createBrowserRouter } from 'react-router-dom';
import { ClientLoginPage } from "./client/ClientLoginPage";
import { ClientPlansPage } from "./client/ClientPlansPage";
import { ClientAccountPage } from "./client/ClientAccountPage";
import { ClientServersPage } from "./client/ClientServersPage";
import { ClientStripeSuccessPage } from "./client/ClientStripeSuccessPage";
import { ClientStripeCancelPage } from "./client/ClientStripeCancelPage";
import { ClientProtectedRoute } from "./client/ClientProtectedRoute";
import { ClientLandingPage } from "./client/ClientLandingPage";
import ClientRegisterPage from "./client/ClientRegisterPage";
import { ClientLayout } from "../components/client/ClientLayout";
import { ClientNodeSelector } from '../components/shared/ClientNodeSelector';
import { ReactElement } from 'react';

const wrapWithLayout = (element: ReactElement) => (
  <ClientLayout>{element}</ClientLayout>
);

export const portalRouter = createBrowserRouter([
    {
        path: "/",
        element: wrapWithLayout(<ClientLandingPage />),
    },
    {
        path: "/login",
        element: wrapWithLayout(<ClientLoginPage />),
    },
    {
        path: "/register",
        element: wrapWithLayout(<ClientRegisterPage />),
    },
    {
        path: "/nodes",
        element: wrapWithLayout(<ClientNodeSelector accountNumber="test" />), // TODO: Get actual account number from auth
    },
    {
        path: "/plans",
        element: wrapWithLayout(<ClientPlansPage />),
    },
    {
        path: "/account",
        element: wrapWithLayout(
            <ClientProtectedRoute>
                <ClientAccountPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/servers",
        element: wrapWithLayout(
            <ClientProtectedRoute>
                <ClientServersPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/checkout/success",
        element: wrapWithLayout(
            <ClientProtectedRoute>
                <ClientStripeSuccessPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/checkout/cancel",
        element: wrapWithLayout(<ClientStripeCancelPage />),
    },
]);