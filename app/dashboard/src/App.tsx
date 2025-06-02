import "react-datepicker/dist/react-datepicker.css";
import "react-loading-skeleton/dist/skeleton.css";
import { RouterProvider } from "react-router-dom";
import { adminRouter } from "./pages/AdminRouter";

function App() {
    return (
        <main className="p-8">
            <RouterProvider router={adminRouter} />
        </main>
    );
}

export default App;