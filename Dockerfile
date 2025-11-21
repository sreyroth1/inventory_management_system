# Use Nginx as a lightweight web server
FROM nginx:alpine

# Copy your website files into Nginx default directory
COPY . /usr/share/nginx/html

# Expose port 80 to the web
EXPOSE 80