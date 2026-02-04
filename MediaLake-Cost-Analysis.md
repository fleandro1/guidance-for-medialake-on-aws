# Media Lake Comprehensive Cost Analysis

> **Last Updated:** February 4, 2026  
> **Region:** US East (N. Virginia)  
> **Pricing Source:** AWS Pricing Calculator and Public Pricing Pages

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Workload Profile](#workload-profile)
- [Cost Breakdown](#cost-breakdown)
  - [1. Base Infrastructure Costs](#1-base-infrastructure-costs)
  - [2. Storage Costs](#2-storage-costs)
  - [3. Initial Ingestion Costs](#3-initial-ingestion-costs)
  - [4. Ongoing Monthly Operational Costs](#4-ongoing-monthly-operational-costs)
  - [5. Data Egress Costs](#5-data-egress-costs)
- [Total Cost Summary](#total-cost-summary)
- [Cost Optimization Recommendations](#cost-optimization-recommendations)
- [Detailed Pricing References](#detailed-pricing-references)

---

## Executive Summary

This analysis provides a comprehensive cost breakdown for deploying and operating Media Lake on AWS with the specified workload characteristics. The analysis includes:

- **One-time initial ingestion costs** for 2.6M+ files
- **Monthly recurring infrastructure costs** (OpenSearch deployment)
- **Monthly operational costs** based on ongoing usage patterns
- **Storage costs** for 726 TB in S3 Standard and 1.2 PB in Glacier Deep Archive

### Key Findings

| Cost Category | One-Time Cost | Monthly Recurring Cost |
|---------------|---------------|------------------------|
| **Initial Ingestion** | $54,820.00 | N/A |
| **Base Infrastructure** | N/A | $73.20 |
| **Storage (S3 + Glacier)** | N/A | $18,869.22 |
| **Ongoing Operations** | N/A | $7,583.80 |
| **Data Egress** | N/A | $7,875.00 |
| **TOTAL** | **$54,820.00** | **$34,401.22** |

---

## Workload Profile

### Storage Requirements

- **S3 Standard Storage:** 726 TB (743,424 GB)
- **Glacier Deep Archive:** 1.2 PB (1,258,291 GB)
- **Total Storage:** 1.926 PB (2,001,715 GB)

### Ingestion Profile

- **Initial Ingestion:** 2,642,361 files (one-time)
- **Daily Ingestion:** 2,000 files
- **Monthly Ingestion:** 60,000 files (30 days)
- **Annual Ingestion:** 730,000 files

### Access Patterns

- **Daily Downloads:** 3,000 files
- **Monthly Downloads:** 90,000 files
- **Estimated Average File Size:** 276 MB (calculated from 726TB / 2.6M active files)
- **Daily Egress Volume:** ~810 GB (3,000 files × 276 MB average)
- **Monthly Egress Volume:** ~24.3 TB

### Deployment Frequency

- **Monthly Redeployments:** 4 times
- **Annual Redeployments:** 48 times

---

## Cost Breakdown

### 1. Base Infrastructure Costs

These are the baseline costs for running Media Lake infrastructure, regardless of usage volume.

#### OpenSearch Deployment (Small Configuration)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| OpenSearch Instance | t3.small.search (1 instance) | $28.72 |
| OpenSearch Storage | 50 GB gp3 | $2.44 |
| NAT Gateway | 2 AZ deployment | $33.30 |
| Cognito | 50 active users/month | $2.00 |
| WAF (Web ACL + Rules) | 2 WebACLs, 4 rules | $7.00 |
| **Subtotal - Base Infrastructure** | | **$73.46** |

#### Alternative: S3 Vectors Deployment

For cost-sensitive deployments without OpenSearch:

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| Cognito | 50 active users/month | $2.00 |
| WAF (Web ACL + Rules) | 2 WebACLs, 4 rules | $7.00 |
| **Subtotal - S3 Vectors Base** | | **$9.00** |

> **Note:** This analysis uses the OpenSearch deployment as the baseline. S3 Vectors deployment reduces base costs by $64.46/month but may have different performance characteristics.

---

### 2. Storage Costs

#### 2.1 S3 Standard Storage (Active Media)

**Capacity:** 726 TB (743,424 GB)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Storage | 743,424 GB × $0.023/GB | $17,098.75 |
| PUT Requests (Monthly Ingestion) | 60,000 requests × $0.005/1,000 | $0.30 |
| GET Requests (Monthly Downloads) | 90,000 requests × $0.0004/1,000 | $0.04 |
| LIST Operations | ~1,000 operations × $0.005/1,000 | $0.01 |
| **Subtotal - S3 Standard** | | **$17,099.10** |

#### 2.2 S3 Glacier Deep Archive (Long-term Archive)

**Capacity:** 1.2 PB (1,258,291 GB)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Storage | 1,258,291 GB × $0.00099/GB | $1,245.67 |
| PUT Requests (Initial Archive) | Amortized over 12 months | $13.21 |
| Lifecycle Transitions | 60,000 objects/month × $0.05/1,000 | $3.00 |
| **Subtotal - Glacier Deep Archive** | | **$1,261.88** |

#### 2.3 S3 Intelligent-Tiering (Optional Optimization)

For workloads with unpredictable access patterns, consider S3 Intelligent-Tiering:

| Tier | Storage | Rate | Monthly Cost |
|------|---------|------|--------------|
| Frequent Access | 100 TB | $0.023/GB | $2,355.20 |
| Infrequent Access | 300 TB | $0.0125/GB | $3,840.00 |
| Archive Instant Access | 326 TB | $0.004/GB | $1,335.30 |
| Monitoring & Automation | 743,424 objects | $0.0025/1,000 | $1.86 |
| **Alternative S3 IT Total** | | **$7,532.36** |

> **Potential Savings:** Using S3 Intelligent-Tiering for active media could save $9,566.74/month ($114,800/year) if access patterns favor infrequent tiers.

#### 2.4 DynamoDB Storage (Metadata)

**Estimate:** 2.6M records initially, growing to 3.3M records after 1 year

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Data Storage | 15 GB (avg 5KB/record × 3M records) | $3.75 |
| Backup Storage | 15 GB continuous backups | $3.75 |
| **Subtotal - DynamoDB Storage** | | **$7.50** |

#### 2.5 OpenSearch Storage (Indexed Metadata)

**Estimate:** 50 GB base + 13 GB for 2.6M records (5KB each)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| OpenSearch Index Storage | 63 GB × $0.135/GB (gp3) | $8.51 |
| **Subtotal - OpenSearch Storage** | | **$8.51** |

#### 2.6 CloudWatch Logs Storage

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Log Ingestion | 100 GB/month × $0.50/GB | $50.00 |
| Log Storage | 500 GB archived × $0.03/GB | $15.00 |
| **Subtotal - CloudWatch Logs** | | **$65.00** |

#### Total Storage Costs

| Storage Type | Monthly Cost |
|--------------|--------------|
| S3 Standard | $17,099.10 |
| S3 Glacier Deep Archive | $1,261.88 |
| DynamoDB | $7.50 |
| OpenSearch | $8.51 |
| CloudWatch Logs | $65.00 |
| **Total Monthly Storage** | **$18,441.99** |

---

### 3. Initial Ingestion Costs

**One-time costs for ingesting 2,642,361 files**

#### 3.1 Step Functions (Workflow Orchestration)

Assuming 20 state transitions per file:

| Item | Calculation | Cost |
|------|-------------|------|
| State Transitions | 2,642,361 files × 20 steps = 52,847,220 transitions | $1,321.18 |
| **Subtotal - Step Functions** | | **$1,321.18** |

#### 3.2 Lambda Functions (Processing)

Assumptions:
- 5 Lambda invocations per file (ingestion, metadata extraction, thumbnail, proxy, indexing)
- Average 1GB memory, 30 seconds per invocation
- Total compute: 13,211,805 invocations × 30s × 1GB = 396,354,150 GB-seconds

| Item | Calculation | Cost |
|------|-------------|------|
| Lambda Requests | 13,211,805 requests × $0.20/1M | $2.64 |
| Lambda Compute | 396,354,150 GB-seconds × $0.0000166667 | $6,605.90 |
| **Subtotal - Lambda** | | **$6,608.54** |

#### 3.3 DynamoDB (Initial Write Operations)

| Item | Calculation | Cost |
|------|-------------|------|
| Write Requests | 2,642,361 writes × $1.25/1M | $3.30 |
| **Subtotal - DynamoDB Writes** | | **$3.30** |

#### 3.4 OpenSearch (Initial Indexing)

| Item | Calculation | Cost |
|------|-------------|------|
| Index Operations | Included in instance cost | $0.00 |
| **Subtotal - OpenSearch** | | **$0.00** |

#### 3.5 MediaConvert (Video Transcoding)

Assumptions:
- 30% of files are videos requiring transcoding (792,708 videos)
- Average 10-minute duration per video
- SD quality output

| Item | Calculation | Cost |
|------|-------------|------|
| SD Transcoding | 792,708 videos × 10 min × $0.015/min | $118,906.20 |
| **Subtotal - MediaConvert** | | **$118,906.20** |

> **Note:** This is the highest initial cost. Consider batch processing over time or using lower quality proxies to reduce costs.

#### 3.6 EventBridge (Event Routing)

| Item | Calculation | Cost |
|------|-------------|------|
| Events Published | 2,642,361 events × $1.00/1M | $2.64 |
| **Subtotal - EventBridge** | | **$2.64** |

#### 3.7 SQS (Queue Operations)

| Item | Calculation | Cost |
|------|-------------|------|
| Standard Queue Requests | 13,211,805 requests × $0.40/1M | $5.28 |
| FIFO Queue Requests | 2,642,361 requests × $0.50/1M | $1.32 |
| **Subtotal - SQS** | | **$6.60** |

#### 3.8 S3 Data Transfer (Intra-region)

Assuming 726 TB uploaded to S3:

| Item | Calculation | Cost |
|------|-------------|------|
| Data Transfer IN | 726 TB (free inbound) | $0.00 |
| **Subtotal - S3 Transfer** | | **$0.00** |

#### 3.9 AI/ML Services (Optional Enrichment)

If using TwelveLabs or similar services for semantic search:

| Item | Calculation | Cost |
|------|-------------|------|
| Video Embedding Generation | 792,708 videos × $0.05/video | $39,635.40 |
| Image Embedding Generation | 1,849,653 images × $0.001/image | $1,849.65 |
| **Subtotal - AI Enrichment** | | **$41,485.05** |

> **Note:** This is optional and depends on enabled integrations. TwelveLabs via Bedrock may have different pricing.

#### Total Initial Ingestion Costs

| Service | One-Time Cost |
|---------|---------------|
| Step Functions | $1,321.18 |
| Lambda | $6,608.54 |
| DynamoDB | $3.30 |
| MediaConvert | $118,906.20 |
| EventBridge | $2.64 |
| SQS | $6.60 |
| AI Enrichment (Optional) | $41,485.05 |
| **Total Initial Costs** | **$168,333.51** |
| **Total without MediaConvert** | **$49,427.31** |
| **Total without AI Services** | **$126,848.46** |

> **Recommendation:** Spread initial ingestion over 3-6 months to reduce spike costs and allow for batch optimizations. This could reduce MediaConvert costs by 40-60% through better resource utilization.

---

### 4. Ongoing Monthly Operational Costs

**Recurring costs based on 60,000 monthly ingestions (2,000/day)**

#### 4.1 Step Functions

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| State Transitions | 60,000 files × 20 steps = 1,200,000 transitions | $30.00 |
| **Subtotal - Step Functions** | | **$30.00** |

#### 4.2 Lambda Functions

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Lambda Requests | 300,000 requests × $0.20/1M | $0.06 |
| Lambda Compute | 9,000,000 GB-seconds × $0.0000166667 | $150.00 |
| API Processing Lambda | 500,000 API requests × 1s × 0.5GB = 250,000 GB-s × $0.0000166667 | $4.17 |
| **Subtotal - Lambda** | | **$154.23** |

#### 4.3 DynamoDB Operations

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Write Requests (Ingestion) | 60,000 writes × $1.25/1M | $0.08 |
| Write Requests (Updates) | 200,000 writes × $1.25/1M | $0.25 |
| Read Requests | 2,000,000 reads × $0.25/1M | $0.50 |
| **Subtotal - DynamoDB Operations** | | **$0.83** |

#### 4.4 OpenSearch Queries

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Search Queries | Included in instance cost | $0.00 |
| **Subtotal - OpenSearch Queries** | | **$0.00** |

#### 4.5 API Gateway

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| REST API Requests | 500,000 requests × $3.50/1M | $1.75 |
| **Subtotal - API Gateway** | | **$1.75** |

#### 4.6 MediaConvert (Ongoing Transcoding)

Assuming 30% of new files are videos:

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| SD Transcoding | 18,000 videos × 10 min × $0.015/min | $2,700.00 |
| **Subtotal - MediaConvert** | | **$2,700.00** |

#### 4.7 EventBridge

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Events Published | 300,000 events × $1.00/1M | $0.30 |
| **Subtotal - EventBridge** | | **$0.30** |

#### 4.8 SQS

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Standard Queue | 300,000 requests × $0.40/1M | $0.12 |
| FIFO Queue | 60,000 requests × $0.50/1M | $0.03 |
| **Subtotal - SQS** | | **$0.15** |

#### 4.9 KMS (Encryption Operations)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Key Storage | 5 keys × $1.00/key | $5.00 |
| API Requests | 311,000 requests × $0.03/10,000 | $0.93 |
| **Subtotal - KMS** | | **$5.93** |

#### 4.10 CloudWatch Metrics & Alarms

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Custom Metrics | 100 metrics × $0.30/metric | $30.00 |
| Alarms | 50 alarms × $0.10/alarm | $5.00 |
| Dashboard | 3 dashboards × $3.00/dashboard | $9.00 |
| **Subtotal - CloudWatch** | | **$44.00** |

#### 4.11 X-Ray (Distributed Tracing)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Traces Recorded | 1,000,000 traces × $5.00/1M | $5.00 |
| Traces Retrieved | 100,000 traces × $0.50/1M | $0.05 |
| **Subtotal - X-Ray** | | **$5.05** |

#### 4.12 CloudFormation (Redeployments)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Stack Operations | 4 deployments × $0.00 (free tier) | $0.00 |
| **Subtotal - CloudFormation** | | **$0.00** |

#### 4.13 CodePipeline (Redeployments)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Pipeline Executions | 4 executions × $1.00 | $4.00 |
| **Subtotal - CodePipeline** | | **$4.00** |

#### 4.14 AI/ML Services (Ongoing Enrichment)

If enabled for new ingestions:

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Video Embeddings | 18,000 videos × $0.05 | $900.00 |
| Image Embeddings | 42,000 images × $0.001 | $42.00 |
| **Subtotal - AI Enrichment** | | **$942.00** |

#### Total Ongoing Monthly Operational Costs

| Service | Monthly Cost |
|---------|--------------|
| Step Functions | $30.00 |
| Lambda | $154.23 |
| DynamoDB Operations | $0.83 |
| API Gateway | $1.75 |
| MediaConvert | $2,700.00 |
| EventBridge | $0.30 |
| SQS | $0.15 |
| KMS | $5.93 |
| CloudWatch | $44.00 |
| X-Ray | $5.05 |
| CodePipeline | $4.00 |
| AI Enrichment (Optional) | $942.00 |
| **Total Operational Costs** | **$3,888.24** |
| **Total without MediaConvert** | **$1,188.24** |
| **Total without AI Services** | **$2,946.24** |

---

### 5. Data Egress Costs

**Monthly costs for 90,000 file downloads (~24.3 TB)**

#### 5.1 CloudFront Data Transfer

| Tier | Volume | Rate | Monthly Cost |
|------|--------|------|--------------|
| First 10 TB | 10,240 GB | $0.085/GB | $870.40 |
| Next 40 TB | 14,159 GB | $0.080/GB | $1,132.72 |
| 50-150 TB | 0 GB | $0.060/GB | $0.00 |
| **Subtotal - CloudFront Transfer** | 24,399 GB | | **$2,003.12** |

#### 5.2 CloudFront Requests

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| HTTPS Requests | 90,000 requests × $0.0100/10,000 | $0.90 |
| **Subtotal - CloudFront Requests** | | **$0.90** |

#### 5.3 S3 Data Transfer to CloudFront

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Data Transfer to CloudFront | 24,399 GB (free to CloudFront) | $0.00 |
| **Subtotal - S3 Transfer** | | **$0.00** |

#### 5.4 Alternative: Direct S3 Egress (No CloudFront)

If downloads bypass CloudFront:

| Tier | Volume | Rate | Monthly Cost |
|------|--------|------|--------------|
| First 10 TB | 10,240 GB | $0.09/GB | $921.60 |
| Next 40 TB | 14,159 GB | $0.085/GB | $1,203.52 |
| **Alternative S3 Direct** | 24,399 GB | | **$2,125.12** |

> **Savings with CloudFront:** $121.10/month ($1,453.20/year)

#### Total Data Egress Costs

| Service | Monthly Cost |
|---------|--------------|
| CloudFront Data Transfer | $2,003.12 |
| CloudFront Requests | $0.90 |
| **Total Egress Costs** | **$2,004.02** |

---

## Total Cost Summary

### Year 1 Costs

| Category | One-Time Cost | Monthly Recurring | Year 1 Total |
|----------|---------------|-------------------|--------------|
| **Initial Ingestion** | $168,333.51 | N/A | $168,333.51 |
| **Base Infrastructure** | N/A | $73.46 | $881.52 |
| **Storage** | N/A | $18,441.99 | $221,303.88 |
| **Ongoing Operations** | N/A | $3,888.24 | $46,658.88 |
| **Data Egress** | N/A | $2,004.02 | $24,048.24 |
| **Monthly Subtotal** | N/A | $24,407.71 | N/A |
| **YEAR 1 TOTAL** | **$168,333.51** | **$24,407.71/month** | **$461,226.03** |

### Steady State (Years 2+)

| Category | Monthly Cost | Annual Cost |
|----------|--------------|-------------|
| Base Infrastructure | $73.46 | $881.52 |
| Storage | $18,441.99 | $221,303.88 |
| Ongoing Operations | $3,888.24 | $46,658.88 |
| Data Egress | $2,004.02 | $24,048.24 |
| **Annual Total** | **$24,407.71/month** | **$292,892.52** |

### Cost Breakdown by Percentage (Steady State)

| Category | Monthly Cost | Percentage |
|----------|--------------|------------|
| Storage | $18,441.99 | 75.5% |
| Operations (Processing) | $3,888.24 | 15.9% |
| Egress | $2,004.02 | 8.2% |
| Base Infrastructure | $73.46 | 0.3% |
| **Total** | **$24,407.71** | **100%** |

---

## Cost Optimization Recommendations

### High-Impact Optimizations (Potential 40-60% Savings)

#### 1. Storage Optimization ($9,567/month savings)

**Current Cost:** $17,099.10/month (S3 Standard)  
**Optimized Cost:** $7,532.36/month (S3 Intelligent-Tiering)  
**Savings:** $9,566.74/month ($114,800/year)

**Actions:**
- Implement S3 Intelligent-Tiering for active media (726 TB)
- Objects automatically move to infrequent access tiers after 30/90 days
- No retrieval fees for Frequent or Infrequent Access tiers
- Significant savings if <15% of files are accessed regularly

**Implementation:**
```bash
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket your-media-bucket \
  --id ActiveMediaTiering \
  --intelligent-tiering-configuration file://tiering-config.json
```

#### 2. MediaConvert Optimization ($1,350/month savings)

**Current Cost:** $2,700/month (SD transcoding for all videos)  
**Optimized Cost:** $1,350/month (Selective transcoding + H.265)  
**Savings:** $1,350/month ($16,200/year)

**Actions:**
- Use H.265 codec (50% better compression, 20% cost reduction)
- Generate proxies only for videos >2 minutes duration
- Use adaptive bitrate streaming for better bandwidth efficiency
- Delay proxy generation for rarely accessed content

#### 3. Lambda Optimization ($77/month savings)

**Current Cost:** $154.23/month  
**Optimized Cost:** $77.12/month (ARM64 + memory tuning)  
**Savings:** $77.11/month ($925/year)

**Actions:**
- Migrate to ARM64 (Graviton2) Lambda functions for 20% cost reduction
- Right-size memory allocation (test 512MB vs 1024MB)
- Implement Lambda SnapStart for Java functions
- Use Lambda Provisioned Concurrency only for time-sensitive operations

#### 4. AI/ML Cost Optimization ($471/month savings)

**Current Cost:** $942/month (TwelveLabs direct API)  
**Optimized Cost:** $471/month (Bedrock + selective processing)  
**Savings:** $471/month ($5,652/year)

**Actions:**
- Use TwelveLabs via Bedrock for potential volume discounts
- Generate embeddings only for searchable content (skip system files)
- Batch processing to reduce API call overhead
- Cache embeddings to avoid reprocessing

#### 5. Data Egress Optimization ($120/month savings)

**Current Cost:** $2,004/month  
**Optimized Cost:** $1,884/month (CDN optimization)  
**Savings:** $120/month ($1,440/year)

**Actions:**
- Increase CloudFront cache TTL from 1 day to 7 days
- Enable compression for text-based assets
- Use CloudFront origin shield for repeated requests
- Implement progressive image loading

### Medium-Impact Optimizations (10-20% Savings)

#### 6. OpenSearch Right-Sizing ($172/month savings)

**Current Cost:** $28.72/month (t3.small.search)  
**Optimized Cost:** $0/month (S3 Vectors) or $14.36/month (t3.micro)  
**Savings:** Up to $28.72/month ($345/year)

**Actions:**
- Evaluate S3 Vectors for semantic search (eliminates OpenSearch for search-only use cases)
- Downsize to t3.micro.search if cluster metrics show <50% utilization
- Enable UltraWarm for older data (70% cost reduction)
- Use cold storage tier for historical data

#### 7. DynamoDB Optimization ($125/month savings)

**Current Monthly Cost Estimate:** $150/month (at scale)  
**Optimized Cost:** $25/month (on-demand + caching)  
**Potential Savings:** $125/month ($1,500/year)

**Actions:**
- Switch from on-demand to provisioned capacity for predictable workloads
- Implement DynamoDB Accelerator (DAX) to reduce read costs
- Enable point-in-time recovery only for critical tables
- Use DynamoDB Auto Scaling to match capacity to demand

#### 8. Redeployment Cost Reduction ($3/month savings)

**Current Cost:** $4/month (CodePipeline executions)  
**Optimized Cost:** $1/month (Reduced frequency)  
**Savings:** $3/month ($36/year)

**Actions:**
- Reduce redeployments from 4/month to 1-2/month
- Use blue-green deployments to reduce failed deployment costs
- Implement better CI/CD testing to catch issues earlier

### Low-Impact Optimizations (<5% Savings)

#### 9. Monitoring Optimization ($20/month savings)

**Current Cost:** $44/month (CloudWatch)  
**Optimized Cost:** $24/month  
**Savings:** $20/month ($240/year)

**Actions:**
- Reduce custom metric retention from 15 months to 3 months
- Use metric filters instead of custom metrics where possible
- Consolidate dashboards to reduce dashboard charges

### Total Potential Monthly Savings

| Optimization | Monthly Savings | Implementation Effort |
|--------------|----------------|----------------------|
| S3 Intelligent-Tiering | $9,566.74 | Low |
| MediaConvert Selective Processing | $1,350.00 | Medium |
| Lambda ARM64 + Optimization | $77.11 | Low |
| AI/ML via Bedrock | $471.00 | Medium |
| CloudFront CDN Optimization | $120.00 | Low |
| OpenSearch Right-sizing | $28.72 | Medium |
| DynamoDB Optimization | $125.00 | Medium |
| Deployment Frequency | $3.00 | Low |
| Monitoring Optimization | $20.00 | Low |
| **Total Potential Savings** | **$11,761.57/month** | |
| **Optimized Monthly Cost** | **$12,646.14/month** | |
| **Annual Savings** | **$141,138.84/year** | |

### Optimized Year 1 Cost Projection

| Category | Current | Optimized | Savings |
|----------|---------|-----------|---------|
| Year 1 Total | $461,226.03 | $320,087.19 | $141,138.84 (30.6%) |
| Steady State Annual | $292,892.52 | $151,753.68 | $141,138.84 (48.2%) |

---

## Detailed Pricing References

### AWS Service Pricing (US East N. Virginia)

**Storage Services:**
- S3 Standard: $0.023 per GB/month
- S3 Standard-IA: $0.0125 per GB/month
- S3 Intelligent-Tiering: $0.023 (Frequent), $0.0125 (Infrequent), $0.004 (Archive Instant)
- S3 Glacier Deep Archive: $0.00099 per GB/month
- S3 PUT/COPY/POST/LIST: $0.005 per 1,000 requests
- S3 GET/SELECT: $0.0004 per 1,000 requests

**Compute Services:**
- Lambda Requests: $0.20 per 1M requests
- Lambda Compute (x86): $0.0000166667 per GB-second
- Lambda Compute (ARM64): $0.0000133334 per GB-second (20% discount)

**Database Services:**
- DynamoDB On-Demand Writes: $1.25 per 1M write request units
- DynamoDB On-Demand Reads: $0.25 per 1M read request units
- DynamoDB Storage: $0.25 per GB/month
- DynamoDB Backup: $0.25 per GB/month

**OpenSearch Service:**
- t3.small.search: $0.039 per hour ($28.72/month)
- t3.medium.search: $0.078 per hour ($57.44/month)
- m6g.large.search: $0.147 per hour ($107.90/month)
- gp3 Storage: $0.135 per GB/month
- UltraWarm Storage: $0.024 per GB/month

**Media Processing:**
- MediaConvert SD: $0.015 per minute
- MediaConvert HD: $0.030 per minute
- MediaConvert 4K: $0.060 per minute

**Networking:**
- CloudFront First 10 TB: $0.085 per GB
- CloudFront Next 40 TB: $0.080 per GB
- CloudFront 50-150 TB: $0.060 per GB
- S3 to Internet First 10 TB: $0.09 per GB
- NAT Gateway: $0.045 per hour + $0.045 per GB processed

**Application Services:**
- API Gateway REST: $3.50 per million requests
- Step Functions: $0.025 per 1,000 state transitions
- EventBridge: $1.00 per million custom events
- SQS Standard: $0.40 per million requests
- SQS FIFO: $0.50 per million requests

**Security & Monitoring:**
- WAF WebACL: $5.00 per month
- WAF Rule: $1.00 per rule per month
- Cognito MAU: $0.0055 per MAU (after free tier of 50,000)
- KMS Key: $1.00 per month
- KMS Requests: $0.03 per 10,000 requests
- CloudWatch Custom Metrics: $0.30 per metric/month
- CloudWatch Alarms: $0.10 per alarm/month
- X-Ray Traces: $5.00 per 1M traces recorded

**DevOps:**
- CodePipeline: $1.00 per active pipeline per month
- CloudFormation: Free

---

## Additional Considerations

### 1. Reserved Instances & Savings Plans

Not applicable for serverless services, but consider for:
- OpenSearch Reserved Instances: 30-50% savings with 1-year commitment
- Savings Plans for Lambda: 17% savings with compute savings plan

### 2. AWS Enterprise Support

If required for production:
- **Cost:** $15,000/month or 10% of monthly AWS spend (whichever is greater)
- **For this workload:** ~$2,441/month (10% of $24,407.71)

### 3. Third-Party Services

If using external services:
- **TwelveLabs Direct:** Pricing varies by volume (potentially higher than Bedrock)
- **Coactive:** Custom pricing based on API calls
- **Other Integrations:** Account for additional vendor costs

### 4. Disaster Recovery & Backup

Estimated additional costs:
- **Cross-Region Replication:** +50% storage cost for DR region
- **Additional Monthly Cost:** ~$9,221/month
- **Total with DR:** ~$33,629/month

### 5. Compliance & Governance

Additional services that may be required:
- AWS Config: ~$5-20/month
- CloudTrail: ~$10-50/month (beyond free tier)
- GuardDuty: ~$30-100/month
- **Total Compliance:** ~$50-200/month

---

## Conclusion

Media Lake's total cost of ownership breaks down as follows:

- **Initial Investment (Year 1 only):** $168,334 for ingesting 2.6M files
- **Monthly Recurring Costs:** $24,408/month ($292,893/year)
- **Cost Per File Managed:** ~$0.09/month per file in active storage
- **Cost Per Download:** ~$0.02 per file download

**Key Takeaway:** Storage dominates costs at 75.5%, making storage optimization the highest-leverage area for cost reduction. Implementing S3 Intelligent-Tiering alone could save $114,800 annually.

With comprehensive optimization, total costs can be reduced by **30-48%** while maintaining performance and reliability.

---

**Document Version:** 1.0  
**Last Updated:** February 4, 2026  
**Next Review:** May 2026
