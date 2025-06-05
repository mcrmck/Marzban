import { createHashRouter } from "react-router-dom";
import { fetch } from "../../lib/api/http";
import { Dashboard } from "../../pages/admin/Dashboard";
import Login from "../shared/Login";

const fetchAdminLoader = async () => {
    try {
        const result = await fetch.get("/admin");
        console.log("Admin loader success:", result);
        return result;
    } catch (error) {
        console.error("Admin loader failed:", error);
        throw error;
    }
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