# Terraform AWS EKS Infrastructure

Terraform modules để triển khai infrastructure cho Crypto Trading Platform lên AWS EKS.

## Cấu Trúc

```
terraform/
├── main.tf                    # Root module
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── versions.tf                # Provider versions
├── terraform.tfvars.example   # Example configuration
│
├── modules/
│   ├── vpc/                   # VPC, subnets, NAT gateway
│   ├── eks/                   # EKS cluster và node groups
│   ├── iam/                   # IAM roles và policies
│   ├── ecr/                   # ECR repositories
│   └── addons/                # EKS add-ons (ALB Controller, etc.)
│
└── environments/
    └── dev/                   # Environment-specific configs
```

## Prerequisites

- Terraform >= 1.5.0
- AWS CLI configured với credentials
- kubectl installed
- Helm 3.x installed

## Quick Start

### 1. Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars với các giá trị phù hợp
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Plan Deployment

```bash
terraform plan
```

### 4. Apply Infrastructure

```bash
terraform apply
```

Quá trình này sẽ tạo:
- VPC với public/private subnets
- EKS cluster với managed node groups
- ECR repositories
- IAM roles và policies
- EKS add-ons

**Lưu ý**: Quá trình này có thể mất 15-20 phút.

### 5. Setup Kubeconfig

```bash
# Từ project root
cd scripts
./setup-kubeconfig.sh [CLUSTER_NAME] [REGION]
```

## Modules

### VPC Module

Tạo VPC với:
- 3 public subnets (multi-AZ)
- 3 private subnets (multi-AZ)
- Internet Gateway
- NAT Gateways (1 per AZ hoặc single cho cost optimization)
- Security groups cho EKS cluster, nodes, và ALB
- VPC endpoints cho S3 và ECR (optional)

### EKS Module

Tạo EKS cluster với:
- Managed node groups:
  - `application`: Cho frontend/backend (t3.large)
  - `data-processing`: Cho Spark/Kafka (t3.xlarge)
  - `system`: Cho monitoring (t3.medium)
- EKS add-ons:
  - VPC CNI
  - Kube-proxy
  - CoreDNS
  - EBS CSI Driver (với IRSA)

### IAM Module

Tạo IAM roles:
- EKS Cluster Service Role
- Node Group Role
- IRSA roles cho:
  - ALB Controller
  - EBS CSI Driver
  - Cluster Autoscaler

### ECR Module

Tạo ECR repositories:
- `crypto-frontend-next`
- `crypto-backend-fastapi`
- `crypto-binance-producer`
- `spark-crypto`
- `airflow-crypto`

Mỗi repository có lifecycle policy để giữ lại 10 images mới nhất.

### Add-ons Module

Deploy các add-ons:
- AWS Load Balancer Controller (với IRSA)
- Metrics Server
- Cluster Autoscaler (với IRSA)

## Configuration

### Variables

Xem `variables.tf` để biết tất cả các variables có sẵn.

**Required**:
- `aws_region`: AWS region
- `cluster_name`: Tên EKS cluster
- `environment`: Environment name (dev/staging/prod)

**Optional**:
- `vpc_cidr`: VPC CIDR block (default: 10.0.0.0/16)
- `node_instance_types`: Instance types cho node groups
- `node_groups_config`: Scaling configuration
- `enable_public_access`: Enable public API endpoint
- `allowed_cidr_blocks`: CIDR blocks allowed to access cluster

### Example terraform.tfvars

```hcl
aws_region = "ap-southeast-1"
cluster_name = "crypto-eks"
environment = "dev"

node_instance_types = {
  application     = ["t3.large"]
  data_processing = ["t3.xlarge"]
  system          = ["t3.medium"]
}

node_groups_config = {
  application = {
    min_size     = 2
    max_size     = 5
    desired_size = 2
  }
  data_processing = {
    min_size     = 2
    max_size     = 4
    desired_size = 2
  }
  system = {
    min_size     = 2
    max_size     = 3
    desired_size = 2
  }
}
```

## Outputs

Sau khi apply, Terraform sẽ output:
- `cluster_id`: EKS cluster ID
- `cluster_endpoint`: EKS API endpoint
- `vpc_id`: VPC ID
- `private_subnet_ids`: Private subnet IDs
- `public_subnet_ids`: Public subnet IDs
- `ecr_repository_urls`: ECR repository URLs
- `kubeconfig_command`: Command để update kubeconfig

Xem tất cả outputs:
```bash
terraform output
```

## Cost Optimization

1. **Single NAT Gateway**: Set `single_nat_gateway = true` trong terraform.tfvars
2. **VPC Endpoints**: Đã được enable để giảm NAT costs
3. **Spot Instances**: Có thể cấu hình node groups với `capacity_type = "SPOT"`
4. **Right-sizing**: Điều chỉnh instance types và counts phù hợp
5. **Cluster Autoscaling**: Tự động scale down khi không sử dụng

## Security

- Worker nodes chạy trong private subnets
- IAM roles với least privilege
- IRSA cho service accounts
- Encryption at rest cho EBS volumes
- Security groups với restricted access

## Troubleshooting

### Cluster không tạo được

1. Kiểm tra IAM permissions
2. Verify VPC và subnets được tạo thành công
3. Check CloudWatch logs

### Node groups không join cluster

1. Verify security groups allow traffic
2. Check IAM role permissions
3. Verify subnet tags đúng format

### Add-ons không deploy

1. Verify OIDC provider được tạo
2. Check IRSA roles và policies
3. Verify service accounts được tạo trong cluster

## Cleanup

Để xóa toàn bộ infrastructure:

```bash
terraform destroy
```

**Cảnh báo**: Điều này sẽ xóa:
- EKS cluster và tất cả workloads
- VPC và networking
- ECR repositories (images sẽ bị xóa)
- IAM roles và policies

## Next Steps

Sau khi infrastructure được tạo:

1. Setup kubeconfig: `./scripts/setup-kubeconfig.sh`
2. Build và push images: `./scripts/build-and-push-images.sh`
3. Update Kubernetes manifests với ECR URLs
4. Deploy applications

Xem README.md chính để biết chi tiết về deployment.

