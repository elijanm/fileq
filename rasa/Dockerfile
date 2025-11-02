FROM rasa/rasa:3.6.15-full
WORKDIR /app
COPY . /app
EXPOSE 5005
CMD ["run", "--enable-api", "--cors", "*", "--debug"]
