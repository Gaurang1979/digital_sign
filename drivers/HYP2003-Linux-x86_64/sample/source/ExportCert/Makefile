OBJ = $(patsubst %.cpp, %.o, $(wildcard *.cpp))
include ../Rule.mak

all: $(OBJ)
	$(CXX) -w $^ -o exportcert $(SHLIBS)

$(OBJ): %.o: %.cpp
	$(CXX) -w -c $< -o $@
clean:
	rm -f *.o exportcert
