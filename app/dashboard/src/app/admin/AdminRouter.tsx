import { createHashRouter } from "react-router-dom";
import { fetch } from "../../lib/api/http";
import { getAuthToken } from "../../lib/utils/authStorage";
import { Dashboard } from "./Dashboard";
import Login from "../shared/Login";

const fetchAdminLoader = () => {
    return fetch.get("/admin", {
        headers: {
            Authorization: `Bearer ${getAuthToken()}`,
        },
    });
};

export const adminRouter = createHashRouter([
    {
        path: "/",
        element: <Dashboard />,
        errorElement: <Login />,
        loader: fetchAdminLoader,
    },
    {
        path: "/login",
        element: <Login />,
    },
]);