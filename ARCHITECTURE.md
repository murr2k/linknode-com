# Demo Application Architecture

## Overview
A simple microservices demo showcasing Kubernetes capabilities on Rackspace.

## Architecture Components

### 1. Frontend Service
- **Technology**: React.js
- **Port**: 3000
- **Purpose**: User interface for the application
- **Features**:
  - Display greeting messages
  - Show visitor counter
  - Display backend service health

### 2. API Gateway
- **Technology**: Node.js with Express
- **Port**: 8080
- **Purpose**: Route requests to appropriate microservices
- **Endpoints**:
  - `/api/greeting` - Get greeting from greeting service
  - `/api/counter` - Get/update visitor counter
  - `/api/health` - Health check endpoint

### 3. Greeting Service
- **Technology**: Python with Flask
- **Port**: 5000
- **Purpose**: Provide personalized greetings
- **Features**:
  - Random greeting generation
  - Multi-language support
  - Time-based greetings

### 4. Counter Service
- **Technology**: Go
- **Port**: 6000
- **Purpose**: Track visitor count
- **Storage**: Redis
- **Features**:
  - Increment visitor count
  - Get current count
  - Reset functionality

### 5. Redis Cache
- **Purpose**: Persistent storage for counter data
- **Port**: 6379

## Kubernetes Resources

### Deployments
- frontend-deployment (1 replica)
- api-gateway-deployment (2 replicas)
- greeting-service-deployment (2 replicas)
- counter-service-deployment (2 replicas)
- redis-deployment (1 replica)

### Services
- frontend-service (LoadBalancer)
- api-gateway-service (ClusterIP)
- greeting-service (ClusterIP)
- counter-service (ClusterIP)
- redis-service (ClusterIP)

### ConfigMaps
- app-config (environment variables)
- nginx-config (for frontend routing)

### Ingress
- app-ingress (routes external traffic)

## Communication Flow
1. User accesses frontend via LoadBalancer/Ingress
2. Frontend makes API calls to API Gateway
3. API Gateway routes to appropriate microservice
4. Microservices communicate with Redis for data
5. Responses flow back through the chain

## Benefits Demonstrated
- Microservices architecture
- Service discovery
- Load balancing
- Horizontal scaling
- Rolling updates
- Health checks
- Persistent storage