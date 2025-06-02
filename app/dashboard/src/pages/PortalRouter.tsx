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

export const portalRouter = createHashRouter([
    {
        path: "/",
        element: <ClientLandingPage />,
    },
    {
        path: "/login",
        element: <ClientLoginPage />,
    },
    {
        path: "/register",
        element: <ClientRegisterPage />,
    },
    {
        path: "/plans",
        element: <ClientPlansPage />,
    },
    {
        path: "/account",
        element: (
            <ClientProtectedRoute>
                <ClientAccountPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/servers",
        element: (
            <ClientProtectedRoute>
                <ClientServersPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/checkout/success",
        element: (
            <ClientProtectedRoute>
                <ClientStripeSuccessPage />
            </ClientProtectedRoute>
        ),
    },
    {
        path: "/checkout/cancel",
        element: <ClientStripeCancelPage />,
    },
]);