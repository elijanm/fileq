graph TB
API[FastAPI Auth API] --> UserService[UserService]
UserService --> MongoDB[(MongoDB)]
UserService --> Redis[(Redis)]
UserService --> Kratos[Kratos Identity]
UserService --> Lago[Lago Billing]

    MongoDB --> |Stores| UserData[User Profiles & Audit Logs]
    Redis --> |Stores| Sessions[Sessions & Rate Limits]
    Kratos --> |Stores| Identity[Identity & Passwords]
    Lago --> |Stores| Billing[Billing Data]

graph TB
User --> API[FastAPI]
API --> Kratos[Kratos Identity]
API --> MongoDB[(Your RBAC System)]

    Kratos --> |Authentication| Identity[Who are you?]
    MongoDB --> |Authorization| Permissions[What can you do?]

graph TB
API[Your API] --> FeatureService[Feature Management Service]
API --> Lago[Lago Billing]

    FeatureService --> |Check Limits| Database[(Tenant Settings)]
    FeatureService --> |Usage Data| Lago

    Lago --> |Bill Usage| PaymentGateway[Stripe/Payment]
    Lago --> |Subscription Status| Webhook[Your Webhooks]

    Webhook --> |Update Plan| Database
