import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Heading,
  Text,
  VStack,
  HStack,
  Badge,
  Spacer,
  Spinner
} from '@chakra-ui/react';
import { 
  MdSecurity, 
  MdRefresh, 
  MdDownload, 
  MdWarning, 
  MdCheckCircle,
  MdError
} from 'react-icons/md';

interface CertificateInfo {
  subject_name: string;
  valid_from: string;
  valid_until: string;
  is_ca?: boolean;
}

interface NodeCertificate {
  node_name: string;
  certificates: {
    ca_cert: CertificateInfo;
    server_cert: CertificateInfo;
    panel_client_cert: CertificateInfo;
  };
}

interface CertificateStatus {
  ca_certificate: {
    exists: boolean;
    expiring_soon: boolean;
    valid_until: string | null;
  };
  node_certificates: {
    total_nodes: number;
    expiring_soon: string[];
  };
  recommendations: string[];
}

export const CertificateManagement: React.FC = () => {
  const [status, setStatus] = useState<CertificateStatus | null>(null);
  const [caInfo, setCaInfo] = useState<CertificateInfo | null>(null);
  const [nodes, setNodes] = useState<NodeCertificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Fetch certificate status
  const fetchStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/certificates/status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        console.error('Failed to fetch certificate status');
      }
    } catch (error) {
      console.error('Error fetching certificate status:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch CA certificate info
  const fetchCaInfo = async () => {
    try {
      const response = await fetch('/api/admin/certificates/ca', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setCaInfo(data);
      }
    } catch (error) {
      console.error('Failed to fetch CA info:', error);
    }
  };

  // Fetch nodes with certificates
  const fetchNodes = async () => {
    try {
      const nodesResponse = await fetch('/api/admin/nodes', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (nodesResponse.ok) {
        const nodesData = await nodesResponse.json();
        
        // Fetch certificate info for each node
        const nodesCerts = await Promise.all(
          nodesData.map(async (node: any) => {
            try {
              const certResponse = await fetch(`/api/admin/certificates/node/${node.name}`, {
                headers: {
                  'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
              });
              
              if (certResponse.ok) {
                return await certResponse.json();
              }
            } catch (error) {
              console.error(`Failed to fetch certs for ${node.name}:`, error);
            }
            return null;
          })
        );
        
        setNodes(nodesCerts.filter(Boolean));
      }
    } catch (error) {
      console.error('Failed to fetch nodes:', error);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchCaInfo();
    fetchNodes();
  }, []);

  // Regenerate CA certificate
  const regenerateCA = async () => {
    if (!confirm('Are you sure? This will regenerate the CA and require updating all node certificates.')) {
      return;
    }
    
    try {
      setActionLoading('regenerate-ca');
      const response = await fetch('/api/admin/certificates/ca/regenerate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        alert('CA certificate regenerated successfully');
        
        // Refresh data
        fetchStatus();
        fetchCaInfo();
        fetchNodes();
      } else {
        alert('Failed to regenerate CA certificate');
      }
    } catch (error) {
      alert('Failed to regenerate CA certificate');
    } finally {
      setActionLoading(null);
    }
  };

  // Rotate node certificates
  const rotateNodeCerts = async (nodeName: string) => {
    try {
      setActionLoading(`rotate-${nodeName}`);
      const response = await fetch(`/api/admin/certificates/node/${nodeName}/rotate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        alert(`Certificates rotated for ${nodeName}`);
        
        // Refresh data
        fetchStatus();
        fetchNodes();
      } else {
        const errorData = await response.json();
        alert(`Failed to rotate certificates: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      alert(`Failed to rotate certificates: ${error}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Export node certificates
  const exportNodeCerts = async (nodeName: string) => {
    try {
      setActionLoading(`export-${nodeName}`);
      const response = await fetch(`/api/admin/certificates/node/${nodeName}/export`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        alert(`Certificates exported for ${nodeName}. Check /tmp/marzban-certs/${nodeName}/`);
      } else {
        alert('Failed to export certificates');
      }
    } catch (error) {
      alert('Failed to export certificates');
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getCertStatus = (validUntil: string) => {
    const expiry = new Date(validUntil);
    const now = new Date();
    const daysUntilExpiry = Math.floor((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    
    if (daysUntilExpiry < 0) {
      return { color: 'red', text: 'Expired', icon: MdError };
    } else if (daysUntilExpiry <= 30) {
      return { color: 'orange', text: 'Expiring Soon', icon: MdWarning };
    } else {
      return { color: 'green', text: 'Valid', icon: MdCheckCircle };
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="300px">
        <Spinner size="lg" />
      </Box>
    );
  }

  return (
    <VStack gap={6} align="stretch">
      {/* Certificate Status Overview */}
      <Box borderWidth="1px" borderRadius="lg" p={6}>
        <HStack mb={4}>
          <MdSecurity size="24px" />
          <Heading size="md">Certificate Management</Heading>
          <Spacer />
          <Button
            size="sm"
            onClick={() => {
              fetchStatus();
              fetchCaInfo();
              fetchNodes();
            }}
            loading={loading}
          >
            <MdRefresh /> Refresh
          </Button>
        </HStack>
        
        {status?.recommendations && (
          <VStack gap={2} align="stretch">
            {status.recommendations.map((rec, index) => (
              <Box 
                key={index} 
                p={3} 
                borderRadius="md" 
                bg={rec.includes('healthy') ? 'green.50' : 'blue.50'}
                borderLeftWidth="4px"
                borderLeftColor={rec.includes('healthy') ? 'green.400' : 'blue.400'}
              >
                <Text fontSize="sm">{rec}</Text>
              </Box>
            ))}
          </VStack>
        )}
      </Box>

      {/* CA Certificate Section */}
      <Box borderWidth="1px" borderRadius="lg" p={6}>
        <HStack mb={4}>
          <Heading size="md">Certificate Authority (CA)</Heading>
          <Spacer />
          <Button
            colorScheme="red"
            size="sm"
            onClick={regenerateCA}
            loading={actionLoading === 'regenerate-ca'}
          >
            <MdRefresh /> Regenerate CA
          </Button>
        </HStack>
        
        {caInfo ? (
          <VStack align="stretch" gap={3}>
            <HStack>
              <Text fontWeight="bold">Subject:</Text>
              <Text>{caInfo.subject_name}</Text>
            </HStack>
            <HStack>
              <Text fontWeight="bold">Valid From:</Text>
              <Text>{formatDate(caInfo.valid_from)}</Text>
            </HStack>
            <HStack>
              <Text fontWeight="bold">Valid Until:</Text>
              <Text>{formatDate(caInfo.valid_until)}</Text>
              <Badge colorScheme={getCertStatus(caInfo.valid_until).color}>
                {getCertStatus(caInfo.valid_until).text}
              </Badge>
            </HStack>
          </VStack>
        ) : (
          <Box p={4} borderRadius="md" bg="orange.50" borderLeftWidth="4px" borderLeftColor="orange.400">
            <Text fontWeight="bold">No CA Certificate</Text>
            <Text fontSize="sm">No Certificate Authority found. One will be created automatically when needed.</Text>
          </Box>
        )}
      </Box>

      {/* Node Certificates Section */}
      <Box borderWidth="1px" borderRadius="lg" p={6}>
        <Heading size="md" mb={4}>Node Certificates</Heading>
        
        {nodes.length > 0 ? (
          <VStack gap={4} align="stretch">
            {nodes.map((node) => (
              <Box key={node.node_name} borderWidth="1px" borderRadius="md" p={4}>
                <VStack align="stretch" gap={3}>
                  <HStack>
                    <Text fontWeight="bold" fontSize="lg">{node.node_name}</Text>
                    <Spacer />
                    <HStack gap={2}>
                      <Button
                        size="sm"
                        onClick={() => rotateNodeCerts(node.node_name)}
                        loading={actionLoading === `rotate-${node.node_name}`}
                      >
                        <MdRefresh /> Rotate
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => exportNodeCerts(node.node_name)}
                        loading={actionLoading === `export-${node.node_name}`}
                      >
                        <MdDownload /> Export
                      </Button>
                    </HStack>
                  </HStack>
                  
                  <HStack>
                    <Text fontWeight="bold">Server Certificate:</Text>
                    <Text fontSize="sm">{formatDate(node.certificates.server_cert.valid_until)}</Text>
                    <Badge colorScheme={getCertStatus(node.certificates.server_cert.valid_until).color} size="sm">
                      {getCertStatus(node.certificates.server_cert.valid_until).text}
                    </Badge>
                  </HStack>
                  
                  <HStack>
                    <Text fontWeight="bold">Panel Client Certificate:</Text>
                    <Text fontSize="sm">{formatDate(node.certificates.panel_client_cert.valid_until)}</Text>
                    <Badge colorScheme={getCertStatus(node.certificates.panel_client_cert.valid_until).color} size="sm">
                      {getCertStatus(node.certificates.panel_client_cert.valid_until).text}
                    </Badge>
                  </HStack>
                </VStack>
              </Box>
            ))}
          </VStack>
        ) : (
          <Box p={4} borderRadius="md" bg="blue.50" borderLeftWidth="4px" borderLeftColor="blue.400">
            <Text fontWeight="bold">No Node Certificates</Text>
            <Text fontSize="sm">Certificates will be generated automatically when you add nodes.</Text>
          </Box>
        )}
      </Box>
    </VStack>
  );
};

export default CertificateManagement;