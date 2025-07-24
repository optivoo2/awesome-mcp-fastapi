# Deploying to Easypanel

This guide will walk you through the process of deploying this application to Easypanel from a GitHub repository.

## 1. Create a New Project in Easypanel

*   Log in to your Easypanel account.
*   Click on the "New Project" button.
*   Give your project a name and select the appropriate region.

## 2. Connect Your GitHub Account

*   In your project settings, navigate to the "Git" section.
*   Click on "Connect to GitHub" and authorize Easypanel to access your repositories.

## 3. Select the Repository

*   Once your GitHub account is connected, you will see a list of your repositories.
*   Select the repository for this project.

## 4. Configure the Build and Run Commands

*   Easypanel will automatically detect the `Dockerfile` in your repository.
*   The build command will be `docker build -t awesome-mcp-fastapi .`
*   The run command will be `docker run -p 8000:8000 --env-file .env awesome-mcp-fastapi`

## 5. Set Up Environment Variables

*   In the "Environment Variables" section of your project settings, you will need to add the following variables:
    *   `PROJECT_NAME`: The name of your project.
    *   `SECRET_KEY`: A strong, unique secret key.
    *   `DATABASE_URL`: The connection string for your database.
    *   `ALLOWED_ORIGINS`: A comma-separated list of allowed origins for CORS.
    *   `ENVIRONMENT`: Set this to `production`.

## 6. Deploy the Application

*   Once you have configured everything, you can trigger a deployment by pushing a new commit to your GitHub repository.
*   Easypanel will automatically build and deploy the new version of your application.