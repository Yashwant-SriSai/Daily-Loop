FROM node:20-bookworm

# Install Python
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv

WORKDIR /app

# Install Node dependencies
COPY package*.json ./
RUN npm install

# Install Python dependencies
COPY requirements.txt ./
RUN pip3 install --break-system-packages -r requirements.txt

# Copy the rest of the project
COPY . .

# Build the Next.js app
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]