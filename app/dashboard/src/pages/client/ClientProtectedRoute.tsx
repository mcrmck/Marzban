import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useIsAuthenticated, useIsLoadingAuth } from "../../lib/stores";
import { Spinner, Container } from "@chakra-ui/react";

interface ClientProtectedRouteProps {
    children: React.ReactNode;
}

export const ClientProtectedRoute = ({ children }: ClientProtectedRouteProps) => {
    const navigate = useNavigate();
    const location = useLocation();
    const isAuthenticated = useIsAuthenticated();
    const isLoadingAuth = useIsLoadingAuth();

    useEffect(() => {
        if (!isLoadingAuth && !isAuthenticated) {
            // Save the current location they were trying to go to
            navigate("/login", {
                state: { from: location },
                replace: true
            });
        }
    }, [isAuthenticated, isLoadingAuth, navigate, location]);

    if (isLoadingAuth) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    if (!isAuthenticated) {
        return null;
    }

    return <>{children}</>;
};