# Terraform config to deploy Slack Bolt app on AWS Lambda with API Gateway

provider "aws" {
  region = "us-west-1"
  default_tags {
    tags = {
      Project     = "Emoji Handler"
      Environment = "Dev"
      Owner       = "you@example.com"
    }
  }
}

############################
# 1. IAM Role for Lambda
############################
resource "aws_iam_role" "emoji_handler_lambda_exec_role" {
  name = "emoji_handler_lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "emoji_handler_lambda_basic_execution" {
  role       = aws_iam_role.emoji_handler_lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "allow_self_invoke" {
  name = "AllowSelfInvoke"
  role = aws_iam_role.emoji_handler_lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "lambda:InvokeFunction",
          "lambda:GetFunction",
          "secretsmanager:GetSecretValue"
        ],
        Resource = "*"
      }
    ]
  })
}

############################
# 1a. Slack Secrets in Secrets Manager
############################
resource "aws_secretsmanager_secret" "emoji_handler_bot_token" {
  name = "emoji_handler_bot_token"
}

resource "aws_secretsmanager_secret_version" "emoji_handler_bot_token_value" {
  secret_id     = aws_secretsmanager_secret.emoji_handler_bot_token.id
  secret_string = var.EMOJI_HANDLER_BOT_TOKEN
}

resource "aws_secretsmanager_secret" "emoji_handler_signing_secret" {
  name = "emoji_handler_signing_secret"
}

resource "aws_secretsmanager_secret_version" "emoji_handler_signing_secret_value" {
  secret_id     = aws_secretsmanager_secret.emoji_handler_signing_secret.id
  secret_string = var.EMOJI_HANDLER_SIGNING_SECRET
}

resource "aws_secretsmanager_secret" "emoji_handler_user_token" {
  name = "emoji_handler_user_token"
}

resource "aws_secretsmanager_secret_version" "emoji_handler_user_token_value" {
  secret_id     = aws_secretsmanager_secret.emoji_handler_user_token.id
  secret_string = var.EMOJI_HANDLER_USER_TOKEN
}
############################
# 2. Lambda Function
############################
resource "aws_lambda_function" "slack_handler" {
  function_name = "slack_emoji_handler"
  role          = aws_iam_role.emoji_handler_lambda_exec_role.arn
  handler       = "main.handler"
  runtime       = "python3.13"
  timeout       = 10
  memory_size = 512
  architectures = ["arm64"]
  layers = [aws_lambda_layer_version.emoji_handler_app_dependencies.arn]

  filename         = "./slack_lambda_app.zip"  # Replace with your ZIP path
  source_code_hash = filebase64sha256("./slack_lambda_app.zip")

  environment {
    variables = {
      MOD_CHANNEL           = var.MOD_CHANNEL
      bot_token_secret_name = aws_secretsmanager_secret.emoji_handler_bot_token.name
      signing_secret_name   = aws_secretsmanager_secret.emoji_handler_signing_secret.name
      user_token_secret_name = aws_secretsmanager_secret.emoji_handler_user_token.name

    }
  }
}

########################################
# 3. API Gateway and Lambda Integration
########################################
resource "aws_apigatewayv2_api" "emoji_handler_apigateway" {
  name          = "slack-events-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.emoji_handler_apigateway.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.slack_handler.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "slack_events" {
  api_id    = aws_apigatewayv2_api.emoji_handler_apigateway.id
  route_key = "POST /slack/events"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.emoji_handler_apigateway.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_handler.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.emoji_handler_apigateway.execution_arn}/*/*"
}

############################
# 4. Variables for Secrets
############################

variable "EMOJI_HANDLER_USER_TOKEN" {
  type        = string
  description = "Slack bot token (xoxp-...)"
}

variable "EMOJI_HANDLER_BOT_TOKEN" {
  type        = string
  description = "Slack bot token (xoxb-...)"
}

variable "EMOJI_HANDLER_SIGNING_SECRET" {
  type        = string
  description = "Slack signing secret"
}

variable "MOD_CHANNEL" {
  type        = string
  description = "slack channel id"
}

############################
# 5. Log retention (CloudWatch)
############################
resource "aws_cloudwatch_log_group" "emoji_handler_lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.slack_handler.function_name}"
  retention_in_days = 14
}


############################
# 5. Output the API URL so you can paste it into Slack
############################
output "events_api_url" {
  value = "${aws_apigatewayv2_api.emoji_handler_apigateway.api_endpoint}/slack/events"
}

############################
# 5. Create a Lambda Layer version from a local file
############################
resource "aws_lambda_layer_version" "emoji_handler_app_dependencies" {
  layer_name               = "emoji_handler_app_layer"
  filename                 = "./slack_layer.zip"
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["arm64"]  # match your function's arch
  description              = "slack_bolt, python_dotenv, requests"
}
