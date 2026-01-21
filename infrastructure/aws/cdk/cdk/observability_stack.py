"""
Observability stack: CloudWatch alarms, dashboards, and logging.
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_logs as logs,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    Tags,
)
from constructs import Construct


class ObservabilityStack(Stack):
    """Observability infrastructure: CloudWatch alarms and dashboards."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster_name: str,
        service_name: str,
        alb_arn: str,
        database_endpoint: str,
        log_group_name: str = "/ecs/platform-dev",
        lambda_function_name: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SNS Topic for alarms (optional - can be configured later)
        alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            display_name="Platform Dev Alarms",
        )

        # ECS Service Alarms
        # CPU Utilization Alarm
        cpu_alarm = cloudwatch.Alarm(
            self,
            "EcsServiceHighCpu",
            alarm_name="platform-dev-ecs-high-cpu",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "ClusterName": cluster_name,
                    "ServiceName": service_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            alarm_description="Alert when ECS service CPU utilization exceeds 80%",
        )

        # Memory Utilization Alarm
        memory_alarm = cloudwatch.Alarm(
            self,
            "EcsServiceHighMemory",
            alarm_name="platform-dev-ecs-high-memory",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="MemoryUtilization",
                dimensions_map={
                    "ClusterName": cluster_name,
                    "ServiceName": service_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            alarm_description="Alert when ECS service memory utilization exceeds 80%",
        )

        # Extract ALB full name from ARN
        # ARN format: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
        alb_name = alb_arn.split("/")[-1] if "/" in alb_arn else alb_arn.split(":")[-1]
        
        # ALB Alarms
        # HTTP 5xx Errors
        http_5xx_alarm = cloudwatch.Alarm(
            self,
            "ALBHttp5xxErrors",
            alarm_name="platform-dev-alb-5xx-errors",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="HTTPCode_Target_5XX_Count",
                dimensions_map={"LoadBalancer": alb_name},
                statistic="Sum",
                period=Duration.minutes(1),
            ),
            threshold=10,  # Alert if more than 10 errors per minute
            evaluation_periods=2,
            alarm_description="Alert when ALB returns 5xx errors",
        )

        # Target Response Time
        response_time_alarm = cloudwatch.Alarm(
            self,
            "ALBHighResponseTime",
            alarm_name="platform-dev-alb-high-response-time",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="TargetResponseTime",
                dimensions_map={"LoadBalancer": alb_name},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=2.0,  # Alert if response time > 2 seconds
            evaluation_periods=2,
            alarm_description="Alert when ALB target response time exceeds 2 seconds",
        )

        # RDS Alarms
        # Database CPU Utilization
        rds_cpu_alarm = cloudwatch.Alarm(
            self,
            "RDSHighCpu",
            alarm_name="platform-dev-rds-high-cpu",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="CPUUtilization",
                dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            alarm_description="Alert when RDS CPU utilization exceeds 80%",
        )

        # Database Connection Count
        rds_connections_alarm = cloudwatch.Alarm(
            self,
            "RDSHighConnections",
            alarm_name="platform-dev-rds-high-connections",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="DatabaseConnections",
                dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,  # Adjust based on instance type
            evaluation_periods=2,
            alarm_description="Alert when RDS connection count is high",
        )

        # Free Storage Space Alarm
        rds_storage_alarm = cloudwatch.Alarm(
            self,
            "RDSLowStorage",
            alarm_name="platform-dev-rds-low-storage",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="FreeStorageSpace",
                dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=2 * 1024 * 1024 * 1024,  # 2 GB free space
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="Alert when RDS free storage space is low",
        )

        # Deployment Failure Alarms
        
        # ECS Service Deployment Failure - Use EventBridge to capture ECS service events
        # Monitor for ECS service events that indicate deployment issues
        # Note: ECS event structure may vary; this pattern captures service state changes
        ecs_deployment_failure_rule = events.Rule(
            self,
            "EcsDeploymentFailure",
            rule_name="platform-dev-ecs-deployment-failure",
            description="Capture ECS service deployment failure events",
            event_pattern=events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Service Action"],
                detail={
                    "serviceName": [service_name],
                }
            ),
        )
        ecs_deployment_failure_rule.add_target(targets.SnsTopic(alarm_topic))
        
        # Monitor for ECS task failures (tasks stopping unexpectedly)
        ecs_task_failure_rule = events.Rule(
            self,
            "EcsTaskFailure",
            rule_name="platform-dev-ecs-task-failure",
            description="Capture ECS task failure events",
            event_pattern=events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={
                    "clusterArn": [f"arn:aws:ecs:{self.region}:{self.account}:cluster/{cluster_name}"],
                }
            ),
        )
        ecs_task_failure_rule.add_target(targets.SnsTopic(alarm_topic))
        
        # Lambda Function Error Alarm
        if lambda_function_name:
            lambda_errors_alarm = cloudwatch.Alarm(
                self,
                "LambdaFunctionErrors",
                alarm_name="platform-dev-lambda-errors",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": lambda_function_name},
                    statistic="Sum",
                    period=Duration.minutes(1),
                ),
                threshold=5,  # Alert if more than 5 errors per minute
                evaluation_periods=2,
                alarm_description="Alert when Lambda function errors exceed threshold",
            )
            lambda_errors_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
            
            # Lambda Throttles Alarm
            lambda_throttles_alarm = cloudwatch.Alarm(
                self,
                "LambdaFunctionThrottles",
                alarm_name="platform-dev-lambda-throttles",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Throttles",
                    dimensions_map={"FunctionName": lambda_function_name},
                    statistic="Sum",
                    period=Duration.minutes(1),
                ),
                threshold=3,  # Alert if more than 3 throttles per minute
                evaluation_periods=2,
                alarm_description="Alert when Lambda function is throttled",
            )
            lambda_throttles_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        
        # CloudFormation Stack Failure Events
        # Create EventBridge rule to capture CloudFormation stack failures
        # CloudFormation emits events to EventBridge with source "aws.cloudformation"
        # Note: CloudFormation events use a specific structure - we'll match on stack name and status
        stack_names = [
            "PlatformNetworkingDev",
            "PlatformSecurityDev",
            "PlatformDataDev",
            "PlatformComputeDev",
            "PlatformObservabilityDev",
        ]
        
        for stack_name in stack_names:
            # Rule for stack failures - matches CloudFormation stack events
            # Event structure: source=aws.cloudformation, detail-type=CloudFormation Stack Status Change
            stack_failure_rule = events.Rule(
                self,
                f"CloudFormationStackFailure{stack_name.replace('Platform', '').replace('Dev', '')}",
                rule_name=f"platform-dev-cfn-failure-{stack_name.lower()}",
                description=f"Capture failure events for {stack_name}",
                event_pattern=events.EventPattern(
                    source=["aws.cloudformation"],
                    detail_type=["CloudFormation Stack Status Change"],
                    detail={
                        "stack-name": [stack_name],
                        "status-details": {
                            "status": [
                                "CREATE_FAILED",
                                "UPDATE_FAILED",
                                "UPDATE_ROLLBACK_COMPLETE",
                                "UPDATE_ROLLBACK_FAILED",
                                "ROLLBACK_COMPLETE",
                                "ROLLBACK_FAILED",
                            ]
                        }
                    }
                ),
            )
            stack_failure_rule.add_target(targets.SnsTopic(alarm_topic))

        # Add SNS actions to existing alarms (optional)
        # cpu_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        # memory_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        # http_5xx_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # CloudWatch Dashboard with comprehensive metrics
        dashboard = cloudwatch.Dashboard(
            self,
            "PlatformDashboard",
            dashboard_name="platform-dev",
        )

        # ECS Metrics
        ecs_cpu_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="CPUUtilization",
            dimensions_map={
                "ClusterName": cluster_name,
                "ServiceName": service_name,
            },
            statistic="Average",
            period=Duration.minutes(5),
            label="CPU %",
        )

        ecs_memory_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="MemoryUtilization",
            dimensions_map={
                "ClusterName": cluster_name,
                "ServiceName": service_name,
            },
            statistic="Average",
            period=Duration.minutes(5),
            label="Memory %",
        )

        ecs_running_tasks_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="RunningTaskCount",
            dimensions_map={
                "ClusterName": cluster_name,
                "ServiceName": service_name,
            },
            statistic="Average",
            period=Duration.minutes(5),
            label="Running Tasks",
        )

        # ALB Metrics
        alb_request_count_metric = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="RequestCount",
            dimensions_map={"LoadBalancer": alb_name},
            statistic="Sum",
            period=Duration.minutes(1),
            label="Requests",
        )

        alb_healthy_hosts_metric = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HealthyHostCount",
            dimensions_map={"LoadBalancer": alb_name},
            statistic="Average",
            period=Duration.minutes(1),
            label="Healthy Hosts",
        )

        alb_unhealthy_hosts_metric = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="UnHealthyHostCount",
            dimensions_map={"LoadBalancer": alb_name},
            statistic="Average",
            period=Duration.minutes(1),
            label="Unhealthy Hosts",
        )

        alb_http_2xx_metric = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HTTPCode_Target_2XX_Count",
            dimensions_map={"LoadBalancer": alb_name},
            statistic="Sum",
            period=Duration.minutes(1),
            label="2xx Responses",
        )

        alb_http_4xx_metric = cloudwatch.Metric(
            namespace="AWS/ApplicationELB",
            metric_name="HTTPCode_Target_4XX_Count",
            dimensions_map={"LoadBalancer": alb_name},
            statistic="Sum",
            period=Duration.minutes(1),
            label="4xx Responses",
        )

        # RDS Metrics
        rds_cpu_metric = cloudwatch.Metric(
            namespace="AWS/RDS",
            metric_name="CPUUtilization",
            dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
            statistic="Average",
            period=Duration.minutes(5),
            label="CPU %",
        )

        rds_memory_metric = cloudwatch.Metric(
            namespace="AWS/RDS",
            metric_name="FreeableMemory",
            dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
            statistic="Average",
            period=Duration.minutes(5),
            label="Free Memory (bytes)",
        )

        rds_storage_metric = cloudwatch.Metric(
            namespace="AWS/RDS",
            metric_name="FreeStorageSpace",
            dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
            statistic="Average",
            period=Duration.minutes(5),
            label="Free Storage (bytes)",
        )

        rds_read_latency_metric = cloudwatch.Metric(
            namespace="AWS/RDS",
            metric_name="ReadLatency",
            dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
            statistic="Average",
            period=Duration.minutes(5),
            label="Read Latency (ms)",
        )

        rds_write_latency_metric = cloudwatch.Metric(
            namespace="AWS/RDS",
            metric_name="WriteLatency",
            dimensions_map={"DBInstanceIdentifier": database_endpoint.split(".")[0]},
            statistic="Average",
            period=Duration.minutes(5),
            label="Write Latency (ms)",
        )

        # Add widgets to dashboard with better organization
        dashboard.add_widgets(
            # Header section - Key metrics at a glance
            cloudwatch.SingleValueWidget(
                title="ECS Running Tasks",
                metrics=[ecs_running_tasks_metric],
                width=4,
            ),
            cloudwatch.SingleValueWidget(
                title="ECS CPU",
                metrics=[ecs_cpu_metric],
                width=4,
            ),
            cloudwatch.SingleValueWidget(
                title="ECS Memory",
                metrics=[ecs_memory_metric],
                width=4,
            ),
            cloudwatch.SingleValueWidget(
                title="ALB Healthy Hosts",
                metrics=[alb_healthy_hosts_metric],
                width=4,
            ),
            cloudwatch.SingleValueWidget(
                title="RDS CPU",
                metrics=[rds_cpu_metric],
                width=4,
            ),
            cloudwatch.SingleValueWidget(
                title="RDS Connections",
                metrics=[rds_connections_alarm.metric],
                width=4,
            ),
            # ECS Section
            cloudwatch.GraphWidget(
                title="ECS CPU Utilization",
                left=[ecs_cpu_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="ECS Memory Utilization",
                left=[ecs_memory_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="ECS Running Tasks",
                left=[ecs_running_tasks_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            # ALB Section
            cloudwatch.GraphWidget(
                title="ALB Request Count",
                left=[alb_request_count_metric],
                width=12,
                period=Duration.minutes(1),
            ),
            cloudwatch.GraphWidget(
                title="ALB Response Codes",
                left=[
                    alb_http_2xx_metric,
                    alb_http_4xx_metric,
                    http_5xx_alarm.metric,
                ],
                width=12,
                period=Duration.minutes(1),
            ),
            cloudwatch.GraphWidget(
                title="ALB Response Time",
                left=[response_time_alarm.metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="ALB Target Health",
                left=[alb_healthy_hosts_metric],
                right=[alb_unhealthy_hosts_metric],
                width=12,
                period=Duration.minutes(1),
            ),
            # RDS Section
            cloudwatch.GraphWidget(
                title="RDS CPU Utilization",
                left=[rds_cpu_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="RDS Connections",
                left=[rds_connections_alarm.metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="RDS Storage",
                left=[rds_storage_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="RDS Memory",
                left=[rds_memory_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            cloudwatch.GraphWidget(
                title="RDS Latency",
                left=[rds_read_latency_metric],
                right=[rds_write_latency_metric],
                width=12,
                period=Duration.minutes(5),
            ),
            # Logs Section - Deployment Error Logs
            cloudwatch.LogQueryWidget(
                title="Deployment Error Logs",
                log_group_names=[log_group_name],
                query_lines=[
                    "fields @timestamp, @message",
                    "| filter @message like /(?i)(error|exception|fatal|critical|failed|failure|deployment error)/",
                    "| sort @timestamp desc",
                    "| limit 100",
                ],
                view=cloudwatch.LogQueryVisualizationType.TABLE,
                width=24,  # Full width for logs
                height=6,  # Taller widget for better visibility
            ),
        )

        # Tag resources
        Tags.of(dashboard).add("app", "platform")
        Tags.of(dashboard).add("env", "dev")

        # Store references
        self.alarm_topic = alarm_topic
        self.dashboard = dashboard

        # Outputs
        CfnOutput(
            self,
            "DashboardUrl",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard.dashboard_name}",
            description="CloudWatch Dashboard URL",
        )

        CfnOutput(
            self,
            "AlarmTopicArn",
            value=alarm_topic.topic_arn,
            description="SNS topic ARN for alarms",
        )
