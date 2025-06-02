import { createHashRouter } from "react-router-dom";
import { ClientLoginPage } from "./client/ClientLoginPage";
import { ClientPlansPage } from "./client/ClientPlansPage";
import { ClientAccountPage } from "./client/ClientAccountPage";
import { ClientServersPage } from "./client/ClientServersPage";
import { ClientStripeSuccessPage } from "./client/ClientStripeSuccessPage";
import { ClientStripeCancelPage } from "./client/ClientStripeCancelPage";
import { ClientProtectedRoute } from "./client/ClientProtectedRoute";
import { ClientLandingPage } from "./client/ClientLandingPage";
import { ClientRegisterPage } from "./client/ClientRegisterPage";
import { ClientLayout } from "../components/client/ClientLayout";

const wrapWithLayout = (element: JSX.Element) => (
  <ClientLayout>{element}</ClientLayout>
);

export const portalRouter = createHashRouter([
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