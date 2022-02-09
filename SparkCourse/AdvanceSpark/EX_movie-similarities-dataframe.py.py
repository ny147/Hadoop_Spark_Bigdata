from matplotlib.pyplot import show
from pyspark.sql import SparkSession
from pyspark.sql import functions as func
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType
import sys

def computeCosineSimilarity(spark,data):
      # Compute xx, xy and yy columns
    pairScores = data \
      .withColumn("xx", func.col("rating1") * func.col("rating1")) \
      .withColumn("yy", func.col("rating2") * func.col("rating2")) \
      .withColumn("xy", func.col("rating1") * func.col("rating2")) 

    # Compute numerator, denominator and numPairs columns
    calculateSimilarity = pairScores \
      .groupBy("movie1", "movie2") \
      .agg( \
        func.sum(func.col("xy")).alias("numerator"), \
        (func.sqrt(func.sum(func.col("xx"))) * func.sqrt(func.sum(func.col("yy")))).alias("denominator"), \
        func.count(func.col("xy")).alias("numPairs")
      )

    # Calculate score and select only needed columns (movie1, movie2, score, numPairs)
    result = calculateSimilarity \
      .withColumn("score", \
        func.when(func.col("denominator") != 0, func.col("numerator") / func.col("denominator")) \
          .otherwise(0) \
      ).select("movie1", "movie2", "score", "numPairs")

    return result

def getMovieName(movieNames, movieId):
    result = movieNames.filter(func.col("movieID") == movieId) \
        .select("movieTitle").collect()[0]

    return result[0]


### start from below 
spark = SparkSession.builder.appName("movieSimilarities").master("local[*]").getOrCreate()

movieNamesSchema = StructType([ \
                                StructField("movieID",IntegerType(),True),\
                                StructField("movieTitle",StringType(),True)\
                             ])

moviesSchema = StructType([     \
                                StructField("userID",IntegerType(),True),\
                                StructField("movieID",IntegerType(),True),\
                                StructField("rating",IntegerType(),True),\
                                StructField("TimeStamp",LongType(),True)])
# Create a broadcast dataset of movieID and movieTitle.
# Apply ISO-885901 charset
movieNames = spark.read \
      .option("sep", "|") \
      .option("charset", "ISO-8859-1") \
      .schema(movieNamesSchema) \
      .csv("C:/Users/Near/Desktop/SparkCourse/ml-100k/u.item")

# Load up movie data as dataset
movies = spark.read \
      .option("sep", "\t") \
      .schema(moviesSchema) \
      .csv("C:/Users/Near/Desktop/SparkCourse/ml-100k/u.data")
rating = movies.select("userID","movieID","rating")


moviePairs = rating.alias("rating1").join(rating.alias("rating2"),(func.col("rating1.userID") == func.col("rating2.userID")) \
                            & (func.col("rating1.movieId") < func.col("rating2.movieId")))\
                                .select(func.col("rating1.movieID").alias("movie1"),\
                                (func.col("rating2.movieID").alias("movie2")),\
                                (func.col("rating1.rating").alias("rating1")),\
                                (func.col("rating2.rating").alias("rating2")))
moviePairsHighRating = moviePairs.filter( (func.col("rating1") > 3) | (func.col("rating2") > 3))
moviePairsHighRating.show()
moviePairSimilarities = computeCosineSimilarity(spark, moviePairsHighRating ).cache()
if (len(sys.argv) > 1):
    scoreThreshold = 0.97
    coOccurrenceThreshold = 50.0

    movieID = int(sys.argv[1])

    # Filter for movies with this sim that are "good" as defined by
    # our quality thresholds above
    filteredResults = moviePairSimilarities.filter( \
        ((func.col("movie1") == movieID) | (func.col("movie2") == movieID)) & \
          (func.col("score") > scoreThreshold) & (func.col("numPairs") > coOccurrenceThreshold))

    # Sort by quality score.
    results = filteredResults.sort(func.col("score").desc()).take(10)
    
    print ("Top 10 similar movies for " + getMovieName(movieNames, movieID))
    
    for result in results:
        # Display the similarity result that isn't the movie we're looking at
        similarMovieID = result.movie1
        if (similarMovieID == movieID):
          similarMovieID = result.movie2
        
        print(getMovieName(movieNames, similarMovieID) + "\tscore: " \
              + str(result.score) + "\tstrength: " + str(result.numPairs))