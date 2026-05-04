"""AWS Database Templates"""
from provisioner.templates.templates.aws.database.rds_postgres.pulumi import RDSPostgresTemplate
from provisioner.templates.templates.aws.database.rds_postgres_nonprod.pulumi import RDSPostgresNonProdTemplate
from provisioner.templates.templates.aws.database.dynamodb_table.pulumi import DynamoDBTableTemplate

__all__ = [
    "RDSPostgresTemplate",
    "RDSPostgresNonProdTemplate",
    "DynamoDBTableTemplate",
]
